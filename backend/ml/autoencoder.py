import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from typing import Tuple, Optional
import pickle
from pathlib import Path


class Autoencoder(nn.Module):
    def __init__(self, input_dim: int, encoding_dim: int = 8):
        super().__init__()
        
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.BatchNorm1d(16),
            nn.Linear(16, encoding_dim),
            nn.ReLU()
        )
        
        self.decoder = nn.Sequential(
            nn.Linear(encoding_dim, 16),
            nn.ReLU(),
            nn.BatchNorm1d(16),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(0.2),
            nn.Linear(32, input_dim)
        )
    
    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded
    
    def encode(self, x):
        return self.encoder(x)


class AutoencoderModel:
    def __init__(self, input_dim: int = 11, encoding_dim: int = 8, 
                 learning_rate: float = 0.001, device: str = None):
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')
        self.input_dim = input_dim
        self.encoding_dim = encoding_dim
        self.learning_rate = learning_rate
        
        self.model = Autoencoder(input_dim, encoding_dim).to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        
        self.threshold = None
        self.mean_reconstruction_error = None
        self.std_reconstruction_error = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, epochs: int = 50, batch_size: int = 32, 
            validation_split: float = 0.1) -> 'AutoencoderModel':
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        val_size = int(len(X) * validation_split)
        train_size = len(X) - val_size
        train_dataset, val_dataset = torch.utils.data.random_split(
            X_tensor, [train_size, val_size]
        )
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)
        
        self.model.train()
        train_losses = []
        val_losses = []
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch in train_loader:
                self.optimizer.zero_grad()
                reconstructed = self.model(batch)
                loss = self.criterion(reconstructed, batch)
                loss.backward()
                self.optimizer.step()
                epoch_loss += loss.item()
            
            train_losses.append(epoch_loss / len(train_loader))
            
            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch in val_loader:
                    reconstructed = self.model(batch)
                    loss = self.criterion(reconstructed, batch)
                    val_loss += loss.item()
            val_losses.append(val_loss / len(val_loader))
            self.model.train()
        
        self.model.eval()
        with torch.no_grad():
            reconstructed = self.model(X_tensor)
            reconstruction_errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            errors = reconstruction_errors.cpu().numpy()
        
        self.mean_reconstruction_error = np.mean(errors)
        self.std_reconstruction_error = np.std(errors)
        self.threshold = self.mean_reconstruction_error + 2 * self.std_reconstruction_error
        
        self.is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError("Model not fitted yet")
        
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        X_tensor = torch.FloatTensor(X).to(self.device)
        
        self.model.eval()
        with torch.no_grad():
            reconstructed = self.model(X_tensor)
            reconstruction_errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            errors = reconstruction_errors.cpu().numpy()
        
        scores = (errors - self.mean_reconstruction_error) / (self.std_reconstruction_error + 1e-8)
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
        
        vector = []
        for feat in expected_features:
            vector.append(features.get(feat, 0.0))
        
        return np.array(vector, dtype=np.float32)

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'input_dim': self.input_dim,
            'encoding_dim': self.encoding_dim,
            'threshold': self.threshold,
            'mean_reconstruction_error': self.mean_reconstruction_error,
            'std_reconstruction_error': self.std_reconstruction_error,
            'is_fitted': self.is_fitted
        }, path)

    def load(self, path: str) -> 'AutoencoderModel':
        checkpoint = torch.load(path, map_location=self.device)
        self.model = Autoencoder(checkpoint['input_dim'], checkpoint['encoding_dim']).to(self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.learning_rate)
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.threshold = checkpoint['threshold']
        self.mean_reconstruction_error = checkpoint['mean_reconstruction_error']
        self.std_reconstruction_error = checkpoint['std_reconstruction_error']
        self.is_fitted = checkpoint['is_fitted']
        return self
