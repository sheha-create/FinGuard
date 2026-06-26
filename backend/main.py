from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Optional, List
import asyncio
import logging
import os
import csv
import io
import json
from pathlib import Path
from datetime import datetime

from .database.sqlite_db import db
from .ml.trainer import MLTrainer
from .services.feature_extraction import FeatureExtractor
from .services.graph_engine import graph_engine
from .services.websocket_manager import ws_manager
from .models.transaction import Transaction, TransactionCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

trainer = MLTrainer(model_dir="models")
feature_extractor = FeatureExtractor()

ALERT_THRESHOLD = 0.6


async def startup_event():
    logger.info("Initializing database...")
    await db.connect()

    logger.info("Clearing old data for fresh start...")
    await db.clear_all_data()

    logger.info("Training ML models...")
    trainer.train(force_retrain=False)
    logger.info("ML models ready")


async def shutdown_event():
    await db.disconnect()


async def process_transaction(tx_data: dict) -> dict:
    try:
        account = await db.get_account(tx_data['sender'])
        if not account:
            await db.create_account({
                "id": tx_data['sender'],
                "kyc_tier": "low",
                "account_type": "personal"
            })

        account = await db.get_account(tx_data['receiver'])
        if not account:
            await db.create_account({
                "id": tx_data['receiver'],
                "kyc_tier": "low",
                "account_type": "personal"
            })

        features = await feature_extractor.extract_features(tx_data)
        ai_score = trainer.score_transaction(features)

        graph_engine.add_transaction(
            tx_id=tx_data['id'],
            sender=tx_data['sender'],
            receiver=tx_data['receiver'],
            amount=tx_data['amount'],
            timestamp=tx_data['timestamp'],
            risk_score=ai_score
        )

        graph_score = graph_engine.compute_graph_score(tx_data['sender'], tx_data['receiver'])
        final_risk = max(ai_score, graph_score)
        flagged = final_risk >= ALERT_THRESHOLD

        tx_result = {
            **tx_data,
            "ai_score": ai_score,
            "graph_score": graph_score,
            "final_risk": final_risk,
            "flagged": flagged,
            "features": features
        }

        await db.create_transaction(tx_result)
        await db.update_account_stats(tx_data['sender'], is_sender=True, amount=tx_data['amount'])
        await db.update_account_stats(tx_data['receiver'], is_sender=False, amount=tx_data['amount'])

        if flagged:
            patterns = graph_engine.detect_patterns(tx_data['sender'], tx_data['receiver'])

            if patterns:
                for pattern in patterns:
                    alert_data = {
                        "id": f"alert_{tx_data['id']}",
                        "pattern": pattern['type'],
                        "involved_accounts": pattern.get('accounts', [tx_data['sender'], tx_data['receiver']]),
                        "tx_ids": [tx_data['id']],
                        "risk_score": final_risk,
                        "description": f"Detected {pattern['type']} pattern with risk score {final_risk:.2f}"
                    }
                    await db.create_alert(alert_data)
                    await ws_manager.send_alert(alert_data)
            else:
                alert_data = {
                    "id": f"alert_{tx_data['id']}",
                    "pattern": "high_risk",
                    "involved_accounts": [tx_data['sender'], tx_data['receiver']],
                    "tx_ids": [tx_data['id']],
                    "risk_score": final_risk,
                    "description": f"High risk transaction detected with score {final_risk:.2f}"
                }
                await db.create_alert(alert_data)
                await ws_manager.send_alert(alert_data)

        await ws_manager.send_transaction_update(tx_result)
        return tx_result

    except Exception as e:
        logger.error(f"Error processing transaction: {e}")
        raise


async def rebuild_graph_from_db():
    graph_engine.graph.clear()
    transactions = await db.get_recent_transactions(limit=1000)
    for tx in transactions:
        graph_engine.add_transaction(
            tx_id=tx['id'],
            sender=tx['sender'],
            receiver=tx['receiver'],
            amount=tx['amount'],
            timestamp=tx['timestamp'],
            risk_score=tx.get('ai_score', 0),
            skip_cleanup=True
        )
    logger.info(f"Graph rebuilt with {len(transactions)} transactions")


def normalize_row(row: dict) -> dict:
    row_lower = {k.lower().strip(): v for k, v in row.items()}

    sender_keys = ['sender', 'from', 'from_account', 'from_acct', 'sender_id',
                   'sender_account', 'source', 'origin', 'payer', 'debtor', 'sender_name']
    receiver_keys = ['receiver', 'to', 'to_account', 'to_acct', 'receiver_id',
                     'receiver_account', 'destination', 'dest', 'payee', 'creditor', 'receiver_name']
    amount_keys = ['amount', 'value', 'sum', 'total', 'transfer_amount',
                   'tx_amount', 'money', 'balance', 'amt']
    timestamp_keys = ['timestamp', 'date', 'time', 'datetime', 'created',
                      'created_at', 'tx_date', 'transaction_date', 'when', 'transaction_time']
    id_keys = ['id', 'tx_id', 'transaction_id', 'txid', 'ref', 'reference']

    sender = None
    for k in sender_keys:
        if k in row_lower and row_lower[k]:
            sender = str(row_lower[k]).strip()
            break

    receiver = None
    for k in receiver_keys:
        if k in row_lower and row_lower[k]:
            receiver = str(row_lower[k]).strip()
            break

    amount = 0
    for k in amount_keys:
        if k in row_lower and row_lower[k]:
            try:
                amount = float(str(row_lower[k]).replace(',', '').replace('$', '').replace('€', '').replace('£', '').strip())
                break
            except (ValueError, TypeError):
                continue

    timestamp = datetime.utcnow().isoformat()
    for k in timestamp_keys:
        if k in row_lower and row_lower[k]:
            ts = str(row_lower[k]).strip()
            if ts:
                timestamp = ts
                break

    tx_id = None
    for k in id_keys:
        if k in row_lower and row_lower[k]:
            tx_id = str(row_lower[k]).strip()
            break

    return {
        "sender": sender,
        "receiver": receiver,
        "amount": amount,
        "timestamp": timestamp,
        "id": tx_id
    }


async def process_upload_batch(rows: list, source: str) -> dict:
    results = {"total": len(rows), "success": 0, "errors": [], "alerts_generated": 0}

    for i, row in enumerate(rows):
        try:
            normalized = normalize_row(row)

            if not normalized["sender"]:
                results["errors"].append(f"Row {i+1}: No sender found. Columns: {list(row.keys())}")
                continue
            if not normalized["receiver"]:
                results["errors"].append(f"Row {i+1}: No receiver found. Columns: {list(row.keys())}")
                continue
            if normalized["amount"] <= 0:
                results["errors"].append(f"Row {i+1}: Invalid amount")
                continue

            tx_data = {
                "id": normalized["id"] or f"upload_{source}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{i}",
                "sender": normalized["sender"],
                "receiver": normalized["receiver"],
                "amount": normalized["amount"],
                "timestamp": normalized["timestamp"]
            }

            tx_result = await process_transaction(tx_data)
            results["success"] += 1

            if tx_result.get("flagged"):
                results["alerts_generated"] += 1

        except Exception as e:
            results["errors"].append(f"Row {i+1}: {str(e)}")

    await rebuild_graph_from_db()
    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield
    await shutdown_event()


app = FastAPI(
    title="FinGuard - AML Transaction Fraud Analyzer",
    description="Real-time AML and transaction fraud detection system",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse(str(frontend_dir / "index.html"))


@app.post("/transactions/ingest")
async def ingest_transaction(tx: TransactionCreate):
    tx_data = tx.dict()
    tx_data['timestamp'] = tx_data.get('timestamp') or datetime.utcnow().isoformat()
    result = await process_transaction(tx_data)
    await rebuild_graph_from_db()
    return result


@app.get("/transactions")
async def get_transactions(limit: int = 500):
    transactions = await db.get_recent_transactions(limit)
    return {"transactions": transactions}


@app.get("/transactions/{tx_id}")
async def get_transaction(tx_id: str):
    transaction = await db.get_transaction(tx_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.get("/alerts")
async def get_alerts(status: Optional[str] = None, limit: int = 100):
    alerts = await db.get_alerts(status=status, limit=limit)
    return {"alerts": alerts}


@app.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    alert = await db.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@app.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, resolution: str, notes: str = ""):
    if resolution not in ["resolved_false_positive", "confirmed"]:
        raise HTTPException(status_code=400, detail="Invalid resolution type")

    alert = await db.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    await db.resolve_alert(alert_id, resolution, notes)
    return {"status": "resolved", "alert_id": alert_id}


@app.get("/graph/stats")
async def get_graph_stats():
    return graph_engine.get_graph_stats()


@app.post("/graph/rebuild")
async def rebuild_graph_endpoint():
    await rebuild_graph_from_db()
    return {"status": "rebuilt", "stats": graph_engine.get_graph_stats()}


@app.get("/graph/full")
async def get_full_graph():
    graph_data = {"nodes": [], "edges": []}

    for node in graph_engine.graph.nodes():
        out_degree = graph_engine.graph.out_degree(node)
        in_degree = graph_engine.graph.in_degree(node)
        graph_data["nodes"].append({
            "id": node,
            "label": node,
            "out_degree": out_degree,
            "in_degree": in_degree,
            "is_center": False
        })

    for u, v, data in graph_engine.graph.edges(data=True):
        graph_data["edges"].append({
            "source": u,
            "target": v,
            "tx_id": data.get('tx_id'),
            "amount": data.get('amount', 0),
            "risk_score": data.get('risk_score', 0),
            "timestamp": data.get('timestamp')
        })

    return graph_data


@app.get("/graph/{account_id}")
async def get_account_graph(account_id: str, hops: int = 2):
    graph_data = graph_engine.get_account_subgraph(account_id, hops)
    return graph_data


@app.get("/accounts/{account_id}")
async def get_account(account_id: str):
    account = await db.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@app.get("/accounts/{account_id}/transactions")
async def get_account_transactions(account_id: str, limit: int = 100):
    transactions = await db.get_account_transactions(account_id, limit)
    return {"transactions": transactions}


@app.get("/model/info")
async def get_model_info():
    return trainer.get_model_info()


@app.post("/upload/csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    try:
        content = await file.read()
        text = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)

        if not rows:
            return {"total": 0, "success": 0, "errors": ["CSV file is empty"]}

        results = await process_upload_batch(rows, source=file.filename)
        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/upload/json")
async def upload_json(file: UploadFile = File(...)):
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Only JSON files are supported")

    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))

        if isinstance(data, dict):
            for key in ["transactions", "data", "records", "items"]:
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                data = [data]

        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="JSON must be an array or object with transactions/data/records key")

        results = await process_upload_batch(data, source=file.filename)
        return results

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/upload/batch")
async def upload_batch(files: List[UploadFile] = File(...)):
    all_results = {"total_files": len(files), "total_transactions": 0, "success": 0, "errors": [], "alerts_generated": 0}

    for file in files:
        try:
            content = await file.read()

            if file.filename.endswith('.csv'):
                text = content.decode('utf-8')
                reader = csv.DictReader(io.StringIO(text))
                rows = list(reader)
                result = await process_upload_batch(rows, source=file.filename)
            elif file.filename.endswith('.json'):
                data = json.loads(content.decode('utf-8'))
                if isinstance(data, dict):
                    for key in ["transactions", "data", "records", "items"]:
                        if key in data and isinstance(data[key], list):
                            data = data[key]
                            break
                    else:
                        data = [data]
                result = await process_upload_batch(data, source=file.filename)
            else:
                all_results["errors"].append(f"{file.filename}: Unsupported format (use .csv or .json)")
                continue

            all_results["total_transactions"] += result.get("total", 0)
            all_results["success"] += result.get("success", 0)
            all_results["alerts_generated"] += result.get("alerts_generated", 0)
            all_results["errors"].extend(result.get("errors", []))

        except Exception as e:
            all_results["errors"].append(f"{file.filename}: {str(e)}")

    return all_results


@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "ml_models": trainer.get_model_info(),
        "graph_stats": graph_engine.get_graph_stats(),
        "websocket_connections": ws_manager.connection_count
    }
