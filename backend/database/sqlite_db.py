import aiosqlite
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager


DATABASE_PATH = "finguard.db"


class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._db.commit()

    async def disconnect(self):
        if self._db:
            await self._db.close()

    async def _create_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                kyc_tier TEXT DEFAULT 'low',
                account_type TEXT DEFAULT 'personal',
                created_at TEXT NOT NULL,
                risk_velocity_matrix TEXT DEFAULT '{}',
                transaction_count INTEGER DEFAULT 0,
                total_sent REAL DEFAULT 0.0,
                total_received REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                amount REAL NOT NULL,
                timestamp TEXT NOT NULL,
                ai_score REAL DEFAULT 0.0,
                graph_score REAL DEFAULT 0.0,
                final_risk REAL DEFAULT 0.0,
                flagged INTEGER DEFAULT 0,
                features TEXT DEFAULT '{}',
                FOREIGN KEY (sender) REFERENCES accounts(id),
                FOREIGN KEY (receiver) REFERENCES accounts(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                pattern TEXT NOT NULL,
                involved_accounts TEXT NOT NULL,
                tx_ids TEXT NOT NULL,
                risk_score REAL NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'open',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolution_notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender);
            CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver);
            CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_transactions_flagged ON transactions(flagged);
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
            CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);
        """)

    async def create_account(self, account_data: dict) -> dict:
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT OR IGNORE INTO accounts (id, kyc_tier, account_type, created_at, 
               risk_velocity_matrix, transaction_count, total_sent, total_received)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                account_data.get("id"),
                account_data.get("kyc_tier", "low"),
                account_data.get("account_type", "personal"),
                now,
                json.dumps(account_data.get("risk_velocity_matrix", {})),
                account_data.get("transaction_count", 0),
                account_data.get("total_sent", 0.0),
                account_data.get("total_received", 0.0),
            )
        )
        await self._db.commit()
        return account_data

    async def get_account(self, account_id: str) -> Optional[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def update_account_stats(self, account_id: str, is_sender: bool, amount: float):
        if is_sender:
            await self._db.execute(
                """UPDATE accounts SET 
                   transaction_count = transaction_count + 1,
                   total_sent = total_sent + ?
                   WHERE id = ?""",
                (amount, account_id)
            )
        else:
            await self._db.execute(
                """UPDATE accounts SET 
                   transaction_count = transaction_count + 1,
                   total_received = total_received + ?
                   WHERE id = ?""",
                (amount, account_id)
            )
        await self._db.commit()

    async def create_transaction(self, tx_data: dict) -> dict:
        await self._db.execute(
            """INSERT INTO transactions 
               (id, sender, receiver, amount, timestamp, ai_score, graph_score, final_risk, flagged, features)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tx_data.get("id"),
                tx_data.get("sender"),
                tx_data.get("receiver"),
                tx_data.get("amount"),
                tx_data.get("timestamp", datetime.utcnow().isoformat()),
                tx_data.get("ai_score", 0.0),
                tx_data.get("graph_score", 0.0),
                tx_data.get("final_risk", 0.0),
                1 if tx_data.get("flagged", False) else 0,
                json.dumps(tx_data.get("features", {})),
            )
        )
        await self._db.commit()
        return tx_data

    async def get_transaction(self, tx_id: str) -> Optional[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def get_account_transactions(self, account_id: str, limit: int = 100) -> List[dict]:
        cursor = await self._db.execute(
            """SELECT * FROM transactions 
               WHERE sender = ? OR receiver = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (account_id, account_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_recent_transactions(self, limit: int = 100) -> List[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def create_alert(self, alert_data: dict) -> dict:
        await self._db.execute(
            """INSERT INTO alerts 
               (id, pattern, involved_accounts, tx_ids, risk_score, description, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert_data.get("id"),
                alert_data.get("pattern"),
                json.dumps(alert_data.get("involved_accounts", [])),
                json.dumps(alert_data.get("tx_ids", [])),
                alert_data.get("risk_score", 0.0),
                alert_data.get("description", ""),
                "open",
                datetime.utcnow().isoformat(),
            )
        )
        await self._db.commit()
        return alert_data

    async def get_alerts(self, status: Optional[str] = None, limit: int = 100) -> List[dict]:
        if status:
            cursor = await self._db.execute(
                "SELECT * FROM alerts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_alert(self, alert_id: str) -> Optional[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM alerts WHERE id = ?", (alert_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None

    async def resolve_alert(self, alert_id: str, resolution: str, notes: str = "") -> bool:
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """UPDATE alerts 
               SET status = ?, resolved_at = ?, resolution_notes = ?
               WHERE id = ?""",
            (resolution, now, notes, alert_id)
        )
        await self._db.commit()
        return True

    async def clear_all_data(self):
        await self._db.execute("DELETE FROM alerts")
        await self._db.execute("DELETE FROM transactions")
        await self._db.execute("DELETE FROM accounts")
        await self._db.commit()

    async def get_account_history(self, account_id: str, hours: int = 168) -> List[dict]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = await self._db.execute(
            """SELECT * FROM transactions 
               WHERE (sender = ? OR receiver = ?) AND timestamp > ?
               ORDER BY timestamp ASC""",
            (account_id, account_id, cutoff)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_transaction_count_in_window(self, account_id: str, hours: int = 24) -> int:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        cursor = await self._db.execute(
            """SELECT COUNT(*) FROM transactions 
               WHERE (sender = ? OR receiver = ?) AND timestamp > ?""",
            (account_id, account_id, cutoff)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_total_amount_in_window(self, account_id: str, hours: int = 24, as_sender: bool = True) -> float:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        field = "sender" if as_sender else "receiver"
        cursor = await self._db.execute(
            f"""SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE {field} = ? AND timestamp > ?""",
            (account_id, cutoff)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0.0


db = Database()
