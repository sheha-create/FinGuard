import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from ..database.sqlite_db import db


class FeatureExtractor:
    def __init__(self):
        self.feature_names = [
            'amount', 'amount_zscore', 'velocity_1h', 'velocity_24h', 'velocity_7d',
            'time_since_last', 'sender_age_days', 'receiver_age_days',
            'sender_out_degree', 'receiver_in_degree', 'amount_ratio_to_mean'
        ]

    async def extract_features(self, transaction: dict) -> Dict[str, Any]:
        sender = transaction['sender']
        receiver = transaction['receiver']
        amount = transaction['amount']
        
        sender_history = await db.get_account_history(sender, hours=168)
        receiver_history = await db.get_account_history(receiver, hours=168)
        
        sender_stats = self._compute_account_stats(sender_history, sender)
        receiver_stats = self._compute_account_stats(receiver_history, receiver)
        
        features = {
            'amount': amount,
            'amount_zscore': self._compute_amount_zscore(amount, sender_stats),
            'velocity_1h': await db.get_transaction_count_in_window(sender, hours=1),
            'velocity_24h': await db.get_transaction_count_in_window(sender, hours=24),
            'velocity_7d': await db.get_transaction_count_in_window(sender, hours=168),
            'time_since_last': self._compute_time_since_last(sender_history, sender),
            'sender_age_days': sender_stats.get('age_days', 0),
            'receiver_age_days': receiver_stats.get('age_days', 0),
            'sender_out_degree': sender_stats.get('out_degree', 0),
            'receiver_in_degree': receiver_stats.get('in_degree', 0),
            'amount_ratio_to_mean': self._compute_amount_ratio(amount, sender_stats)
        }
        
        return features

    def _compute_account_stats(self, history: List[dict], account_id: str) -> Dict[str, Any]:
        if not history:
            return {
                'age_days': 0,
                'total_amount': 0,
                'mean_amount': 0,
                'std_amount': 0,
                'transaction_count': 0,
                'out_degree': 0,
                'in_degree': 0
            }
        
        sent_txs = [tx for tx in history if tx['sender'] == account_id]
        received_txs = [tx for tx in history if tx['receiver'] == account_id]
        
        all_amounts = [tx['amount'] for tx in history]
        
        if history:
            first_tx_time = min(datetime.fromisoformat(tx['timestamp']) for tx in history)
            age_days = (datetime.utcnow() - first_tx_time).days
        else:
            age_days = 0
        
        out_degree = len(set(tx['receiver'] for tx in sent_txs))
        in_degree = len(set(tx['sender'] for tx in received_txs))
        
        return {
            'age_days': age_days,
            'total_amount': sum(all_amounts),
            'mean_amount': np.mean(all_amounts) if all_amounts else 0,
            'std_amount': np.std(all_amounts) if len(all_amounts) > 1 else 0,
            'transaction_count': len(history),
            'out_degree': out_degree,
            'in_degree': in_degree
        }

    def _compute_amount_zscore(self, amount: float, sender_stats: dict) -> float:
        mean = sender_stats.get('mean_amount', 0)
        std = sender_stats.get('std_amount', 0)
        
        if std == 0 or sender_stats.get('transaction_count', 0) < 3:
            return 0.0
        
        zscore = (amount - mean) / std
        return float(np.clip(zscore, -5, 5))

    def _compute_time_since_last(self, history: List[dict], account_id: str) -> float:
        if not history:
            return 86400.0
        
        account_txs = [tx for tx in history if tx['sender'] == account_id or tx['receiver'] == account_id]
        
        if not account_txs:
            return 86400.0
        
        timestamps = [datetime.fromisoformat(tx['timestamp']) for tx in account_txs]
        latest = max(timestamps)
        
        time_diff = (datetime.utcnow() - latest).total_seconds()
        return float(min(time_diff, 604800.0))

    def _compute_amount_ratio(self, amount: float, sender_stats: dict) -> float:
        mean = sender_stats.get('mean_amount', 0)
        
        if mean == 0 or sender_stats.get('transaction_count', 0) < 3:
            return 1.0
        
        ratio = amount / mean
        return float(np.clip(ratio, 0.1, 10.0))

    def get_feature_names(self) -> List[str]:
        return self.feature_names.copy()
