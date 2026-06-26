import numpy as np
from typing import Tuple, Optional
from pathlib import Path
import logging

from .isolation_forest import IsolationForestModel
from .autoencoder import AutoencoderModel

logger = logging.getLogger(__name__)


class MLTrainer:
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.if_model = IsolationForestModel(contamination=0.1, n_estimators=100)
        self.ae_model = AutoencoderModel(input_dim=11, encoding_dim=8)
        
        self.feature_names = [
            'amount', 'amount_zscore', 'velocity_1h', 'velocity_24h', 'velocity_7d',
            'time_since_last', 'sender_age_days', 'receiver_age_days',
            'sender_out_degree', 'receiver_in_degree', 'amount_ratio_to_mean'
        ]

    def generate_normal_transactions(self, n_samples: int = 5000) -> np.ndarray:
        np.random.seed(42)
        
        amounts = np.random.lognormal(mean=6, sigma=1.5, size=n_samples)
        amounts = np.clip(amounts, 10, 100000)
        
        amount_zscore = np.random.normal(0, 1, n_samples)
        
        velocity_1h = np.random.poisson(lam=2, size=n_samples).astype(float)
        velocity_24h = np.random.poisson(lam=10, size=n_samples).astype(float)
        velocity_7d = np.random.poisson(lam=50, size=n_samples).astype(float)
        
        time_since_last = np.random.exponential(scale=3600, size=n_samples)
        
        sender_age = np.random.uniform(30, 3650, size=n_samples)
        receiver_age = np.random.uniform(30, 3650, size=n_samples)
        
        sender_out_degree = np.random.poisson(lam=5, size=n_samples).astype(float)
        receiver_in_degree = np.random.poisson(lam=5, size=n_samples).astype(float)
        
        amount_ratio = np.random.normal(1, 0.3, n_samples)
        amount_ratio = np.clip(amount_ratio, 0.1, 5.0)
        
        features = np.column_stack([
            amounts, amount_zscore, velocity_1h, velocity_24h, velocity_7d,
            time_since_last, sender_age, receiver_age,
            sender_out_degree, receiver_in_degree, amount_ratio
        ])
        
        return features

    def generate_anomalous_transactions(self, n_samples: int = 500) -> np.ndarray:
        np.random.seed(123)
        
        n_loop = n_samples // 3
        n_fan_out = n_samples // 3
        n_fan_in = n_samples - n_loop - n_fan_out
        
        loop_amounts = np.random.uniform(9000, 9999, size=n_loop)
        loop_zscore = np.random.normal(3, 0.5, size=n_loop)
        loop_velocity_1h = np.random.poisson(lam=10, size=n_loop).astype(float)
        loop_velocity_24h = np.random.poisson(lam=50, size=n_loop).astype(float)
        loop_velocity_7d = np.random.poisson(lam=100, size=n_loop).astype(float)
        loop_time_since = np.random.exponential(scale=300, size=n_loop)
        loop_sender_age = np.random.uniform(1, 30, size=n_loop)
        loop_receiver_age = np.random.uniform(1, 30, size=n_loop)
        loop_sender_out = np.random.poisson(lam=15, size=n_loop).astype(float)
        loop_receiver_in = np.random.poisson(lam=15, size=n_loop).astype(float)
        loop_amount_ratio = np.random.normal(2.5, 0.5, size=n_loop)
        
        loop_features = np.column_stack([
            loop_amounts, loop_zscore, loop_velocity_1h, loop_velocity_24h, loop_velocity_7d,
            loop_time_since, loop_sender_age, loop_receiver_age,
            loop_sender_out, loop_receiver_in, loop_amount_ratio
        ])
        
        fan_out_amounts = np.random.uniform(8000, 9500, size=n_fan_out)
        fan_out_zscore = np.random.normal(2, 0.5, size=n_fan_out)
        fan_out_velocity_1h = np.random.poisson(lam=8, size=n_fan_out).astype(float)
        fan_out_velocity_24h = np.random.poisson(lam=40, size=n_fan_out).astype(float)
        fan_out_velocity_7d = np.random.poisson(lam=80, size=n_fan_out).astype(float)
        fan_out_time_since = np.random.exponential(scale=600, size=n_fan_out)
        fan_out_sender_age = np.random.uniform(5, 60, size=n_fan_out)
        fan_out_receiver_age = np.random.uniform(5, 60, size=n_fan_out)
        fan_out_sender_out = np.random.poisson(lam=20, size=n_fan_out).astype(float)
        fan_out_receiver_in = np.random.poisson(lam=3, size=n_fan_out).astype(float)
        fan_out_amount_ratio = np.random.normal(2, 0.4, size=n_fan_out)
        
        fan_out_features = np.column_stack([
            fan_out_amounts, fan_out_zscore, fan_out_velocity_1h, fan_out_velocity_24h, fan_out_velocity_7d,
            fan_out_time_since, fan_out_sender_age, fan_out_receiver_age,
            fan_out_sender_out, fan_out_receiver_in, fan_out_amount_ratio
        ])
        
        fan_in_amounts = np.random.uniform(8500, 9800, size=n_fan_in)
        fan_in_zscore = np.random.normal(2.5, 0.5, size=n_fan_in)
        fan_in_velocity_1h = np.random.poisson(lam=8, size=n_fan_in).astype(float)
        fan_in_velocity_24h = np.random.poisson(lam=40, size=n_fan_in).astype(float)
        fan_in_velocity_7d = np.random.poisson(lam=80, size=n_fan_in).astype(float)
        fan_in_time_since = np.random.exponential(scale=600, size=n_fan_in)
        fan_in_sender_age = np.random.uniform(5, 60, size=n_fan_in)
        fan_in_receiver_age = np.random.uniform(5, 60, size=n_fan_in)
        fan_in_sender_out = np.random.poisson(lam=3, size=n_fan_in).astype(float)
        fan_in_receiver_in = np.random.poisson(lam=20, size=n_fan_in).astype(float)
        fan_in_amount_ratio = np.random.normal(2, 0.4, size=n_fan_in)
        
        fan_in_features = np.column_stack([
            fan_in_amounts, fan_in_zscore, fan_in_velocity_1h, fan_in_velocity_24h, fan_in_velocity_7d,
            fan_in_time_since, fan_in_sender_age, fan_in_receiver_age,
            fan_in_sender_out, fan_in_receiver_in, fan_in_amount_ratio
        ])
        
        return np.vstack([loop_features, fan_out_features, fan_in_features])

    def train(self, force_retrain: bool = False) -> dict:
        if_model_path = self.model_dir / "isolation_forest.pkl"
        ae_model_path = self.model_dir / "autoencoder.pth"
        
        if not force_retrain and if_model_path.exists() and ae_model_path.exists():
            logger.info("Loading pre-trained models...")
            self.if_model.load(str(if_model_path))
            self.ae_model.load(str(ae_model_path))
            return {"status": "loaded", "if_fitted": self.if_model.is_fitted, "ae_fitted": self.ae_model.is_fitted}
        
        logger.info("Generating synthetic training data...")
        normal_data = self.generate_normal_transactions(5000)
        anomalous_data = self.generate_anomalous_transactions(500)
        
        all_data = np.vstack([normal_data, anomalous_data])
        np.random.shuffle(all_data)
        
        logger.info("Training Isolation Forest...")
        self.if_model.fit(normal_data)
        self.if_model.save(str(if_model_path))
        
        logger.info("Training Autoencoder...")
        self.ae_model.fit(normal_data, epochs=50, batch_size=32)
        self.ae_model.save(str(ae_model_path))
        
        logger.info("Training complete!")
        return {"status": "trained", "if_fitted": True, "ae_fitted": True}

    def score_transaction(self, features: dict, if_weight: float = 0.4, ae_weight: float = 0.6) -> float:
        if_score = self.if_model.score_transaction(features)
        ae_score = self.ae_model.score_transaction(features)
        
        final_score = if_weight * if_score + ae_weight * ae_score
        return float(np.clip(final_score, 0, 1))

    def get_model_info(self) -> dict:
        return {
            "if_model": {
                "type": "IsolationForest",
                "is_fitted": self.if_model.is_fitted,
                "feature_dim": self.if_model.feature_dim
            },
            "ae_model": {
                "type": "Autoencoder",
                "is_fitted": self.ae_model.is_fitted,
                "input_dim": self.ae_model.input_dim,
                "encoding_dim": self.ae_model.encoding_dim,
                "threshold": self.ae_model.threshold
            }
        }
