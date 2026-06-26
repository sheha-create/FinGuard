import numpy as np
from typing import Optional
import pickle
from pathlib import Path


class AutoencoderModel:
    def __init__(self, input_dim: int = 11, encoding_dim: int = 8):
        self.input_dim = input_dim
        self.encoding_dim = encoding_dim
        self.threshold = None
        self.mean_reconstruction_error = None
        self.std_reconstruction_error = None
        self.is_fitted = False
        self.mean = None
        self.std = None
        self.pca_components = None
        self.pca_mean = None

    def fit(self, X: np.ndarray, **kwargs) -> 'AutoencoderModel':
        self.mean = np.mean(X, axis=0)
        self.std = np.std(X, axis=0) + 1e-8
        X_norm = (X - self.mean) / self.std

        self.pca_mean = np.mean(X_norm, axis=0)
        centered = X_norm - self.pca_mean

        cov = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        idx = np.argsort(eigenvalues)[::-1][:self.encoding_dim]
        self.pca_components = eigenvectors[:, idx].T

        reconstructed = self._reconstruct(X_norm)
        errors = np.mean((X_norm - reconstructed) ** 2, axis=1)

        self.mean_reconstruction_error = np.mean(errors)
        self.std_reconstruction_error = np.std(errors) + 1e-8
        self.threshold = self.mean_reconstruction_error + 2 * self.std_reconstruction_error
        self.is_fitted = True
        return self

    def _reconstruct(self, X_norm: np.ndarray) -> np.ndarray:
        projected = (X_norm - self.pca_mean) @ self.pca_components.T
        reconstructed = projected @ self.pca_components + self.pca_mean
        return reconstructed

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        if X.ndim == 1:
            X = X.reshape(1, -1)
        X_norm = (X - self.mean) / self.std
        reconstructed = self._reconstruct(X_norm)
        errors = np.mean((X_norm - reconstructed) ** 2, axis=1)
        scores = (errors - self.mean_reconstruction_error) / self.std_reconstruction_error
        scores = 1 / (1 + np.exp(-scores))
        return np.clip(scores, 0, 1)

    def score_transaction(self, features: dict) -> float:
        feature_vector = self._dict_to_vector(features)
        return float(self.predict(feature_vector)[0])

    def _dict_to_vector(self, features: dict) -> np.ndarray:
        expected_features = [
            'amount', 'amount_zscore', 'velocity_1h', 'velocity_24h', 'velocity_7d',
            'time_since_last', 'sender_age_days', 'receiver_age_days',
            'sender_out_degree', 'receiver_in_degree', 'amount_ratio_to_mean'
        ]
        return np.array([features.get(f, 0.0) for f in expected_features], dtype=np.float32)

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'input_dim': self.input_dim,
                'encoding_dim': self.encoding_dim,
                'threshold': self.threshold,
                'mean_reconstruction_error': self.mean_reconstruction_error,
                'std_reconstruction_error': self.std_reconstruction_error,
                'is_fitted': self.is_fitted,
                'mean': self.mean,
                'std': self.std,
                'pca_components': self.pca_components,
                'pca_mean': self.pca_mean
            }, f)

    def load(self, path: str) -> 'AutoencoderModel':
        with open(path, 'rb') as f:
            data = pickle.load(f)
        self.input_dim = data['input_dim']
        self.encoding_dim = data['encoding_dim']
        self.threshold = data['threshold']
        self.mean_reconstruction_error = data['mean_reconstruction_error']
        self.std_reconstruction_error = data['std_reconstruction_error']
        self.is_fitted = data['is_fitted']
        self.mean = data['mean']
        self.std = data['std']
        self.pca_components = data['pca_components']
        self.pca_mean = data['pca_mean']
        return self
