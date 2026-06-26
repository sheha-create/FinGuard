# FinGuard - Real-Time AML & Transaction Fraud Analyzer

A streaming system that ingests transfers in real time, scores each one with an ML anomaly model, and continuously updates a transaction graph to detect structural laundering patterns (loops, fan-out/fan-in, rapid pass-through chains).

## Features

- **Real-time Transaction Ingestion**: Async FastAPI endpoint for high-velocity transfer events
- **ML Anomaly Detection**: Isolation Forest + Autoencoder ensemble for scoring
- **Graph Analysis**: NetworkX-based structural pattern detection (loops, fan-out, fan-in)
- **Live Dashboard**: Force-directed graph visualization with D3.js
- **WebSocket Alerts**: Real-time push notifications for suspicious activity
- **Dark Mode UI**: Modern compliance dashboard interface

## Architecture

```
[Transaction Generator] -> [FastAPI Async Ingest] -> [Feature Extractor]
        -> [AI Scoring: Isolation Forest + Autoencoder] -> [Graph Engine]
        -> [SQLite Database] -> [WebSocket push] -> [Dashboard]
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python run.py
```

Or directly with uvicorn:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 3. Access the Dashboard

Open http://localhost:8000 in your browser.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/health` | GET | System health check |
| `/transactions/ingest` | POST | Submit a transaction for scoring |
| `/transactions` | GET | List recent transactions |
| `/alerts` | GET | List alerts (filter by status) |
| `/alerts/{id}/resolve` | POST | Resolve an alert |
| `/graph/{account_id}` | GET | Get account subgraph |
| `/ws/alerts` | WebSocket | Live alert stream |

## Project Structure

```
finguard/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models/              # Pydantic data models
│   ├── services/            # Business logic
│   │   ├── feature_extraction.py
│   │   ├── graph_engine.py
│   │   └── websocket_manager.py
│   ├── ml/                  # ML models
│   │   ├── isolation_forest.py
│   │   ├── autoencoder.py
│   │   └── trainer.py
│   ├── database/            # SQLite operations
│   └── generator/           # Synthetic data generator
├── frontend/
│   ├── index.html           # Dashboard UI
│   ├── css/styles.css       # Dark mode styling
│   └── js/                  # Frontend logic
│       ├── app.js
│       ├── graph.js
│       ├── alerts.js
│       └── websocket.js
├── requirements.txt
└── run.py                   # Entry point
```

## Detection Patterns

- **Loop/Cycle Detection**: Identifies money flowing in circles through multiple accounts
- **Fan-Out Detection**: Detects single account sending to many recipients rapidly
- **Fan-In Detection**: Detects many accounts sending to single recipient
- **High-Risk Transactions**: Transactions exceeding risk thresholds

## ML Models

- **Isolation Forest**: Global outlier detection on transaction features
- **Autoencoder**: Behavioral anomaly detection via reconstruction error
- **Fusion**: Weighted combination (0.4×IF + 0.6×AE) for final score

## Demo

The system includes a synthetic transaction generator that creates:
- Normal transaction traffic
- Structuring patterns (loops, fan-out)
- High-value suspicious transactions

Watch the dashboard for real-time detection of suspicious patterns with red-highlighted graph edges.

## Technology Stack

- **Backend**: FastAPI, SQLite, NetworkX, scikit-learn, PyTorch
- **Frontend**: Vanilla HTML/JS, D3.js
- **ML**: Isolation Forest, Autoencoder (PyTorch)
- **Real-time**: WebSocket
