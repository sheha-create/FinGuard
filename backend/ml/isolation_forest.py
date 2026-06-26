import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pickle
from pathlib import Path
from typing import Tuple, Optional


class IsolationForestModel:
    def __init__(self, contamination: float = 0.1, n_estimators: int = 100):
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42,
            n_jobs=-1
        )
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_dim = None

    def fit(self, X: np.ndarray) -> 'IsolationForestModel':
        self.feature_dim = X.shape[1]
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        if X.shape[1] != self.feature_dim:
            raise ValueError(f"Expected {self.feature_dim} features, got {X.shape[1]}")
        
        X_scaled = self.scaler.transform(X)
        raw_scores = self.model.decision_function(X_scaled)
        
        min_score = raw_scores.min()
        max_score = raw_scores.max()
        if max_score - min_score > 0:
            normalized = (raw_scores - min_score) / (max_score - min_score)
        else:
            normalized = np.full_like(raw_scores, 0.5)
        
        anomaly_scores = 1 - normalized
        return np.clip(anomaly_scores, 0, 1)

    def score_transaction(self, features: dict) -> float:
        feature_vector = self._dict_to_vector(features)
        return float(self.predict(feature_vector)[0])

    def _dict_to_vector(self, features: dict) -> np.ndarray:
        expected_features = [
            'amount', 'amount_zscore', 'velocity_1h', 'velocity_24h', 'velocity_7d',
            'time_since_last', 'sender_age_days', 'receiver_age_days',
            'sender_out_degree', 'receiver_in_degree', 'amount_ratio_to_mean'
        ]
        
        vector = []
        for feat in expected_features:
            vector.append(features.get(feat, 0.0))
        
        return np.array(vector, dtype=np.float32)

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_dim': self.feature_dim,
                'is_fitted': self.is_fitted
            }, f)

    def load(self, path: str) -> 'IsolationForestModel':
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_dim = data['feature_dim']
            self.is_fitted = data['is_fitted']
        return self
