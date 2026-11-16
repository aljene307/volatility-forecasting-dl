"""Réseaux de deep learning du projet (torch) : LSTM, GRU, CNN-LSTM, Transformer encodeur codé à la main.

Règles (config/regles.toml, section entrainement) : sortie = une prévision de log(RV) normalisée ;
dropout des réseaux récurrents appliqué entre les couches ET à la sortie (avec 1 couche : à la sortie).
Le TFT vient de pytorch-forecasting, entraîné avec la perte MSE ci-dessous (pas d'intervalles de quantiles).
"""

from __future__ import annotations

import math

import torch
from torch import nn


class ReseauRecurrent(nn.Module):
    """LSTM ou GRU : séquence (lot, 30 jours, variables) -> prévision du lendemain."""

    def __init__(self, type_cellule: str, n_entrees: int, taille_cachee: int, couches: int, dropout: float):
        super().__init__()
        classe = {"lstm": nn.LSTM, "gru": nn.GRU}[type_cellule]
        self.recurrent = classe(n_entrees, taille_cachee, num_layers=couches, batch_first=True,
                                dropout=dropout if couches > 1 else 0.0)
        self.dropout = nn.Dropout(dropout)
        self.sortie = nn.Linear(taille_cachee, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, _ = self.recurrent(x)
        return self.sortie(self.dropout(h[:, -1, :])).squeeze(-1)


class CnnLstm(nn.Module):
    """Convolution sur le temps (motifs de quelques jours), puis LSTM."""

    def __init__(self, n_entrees: int, filtres: int, noyau: int, taille_cachee: int, couches: int, dropout: float):
        super().__init__()
        self.convolution = nn.Conv1d(n_entrees, filtres, kernel_size=noyau, padding=noyau // 2)
        self.activation = nn.ReLU()
        self.recurrent = ReseauRecurrent("lstm", filtres, taille_cachee, couches, dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.activation(self.convolution(x.transpose(1, 2))).transpose(1, 2)
        return self.recurrent(z)


class AttentionMultiTetes(nn.Module):
    """Attention à plusieurs têtes, écrite à la main : softmax(Q·Kᵀ / racine(d)) · V."""

    def __init__(self, d_model: int, tetes: int, dropout: float):
        super().__init__()
        if d_model % tetes:
            raise ValueError(f"d_model ({d_model}) doit être divisible par le nombre de têtes ({tetes}).")
        self.tetes, self.d_tete = tetes, d_model // tetes
        self.q, self.k, self.v = (nn.Linear(d_model, d_model) for _ in range(3))
        self.sortie = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)
        self.derniers_poids: torch.Tensor | None = None   # gardés pour l'explicabilité

    def _decouper(self, x: torch.Tensor) -> torch.Tensor:
        lot, longueur, _ = x.shape
        return x.view(lot, longueur, self.tetes, self.d_tete).transpose(1, 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        q, k, v = self._decouper(self.q(x)), self._decouper(self.k(x)), self._decouper(self.v(x))
        scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_tete)
        poids = torch.softmax(scores, dim=-1)
        self.derniers_poids = poids.detach()
        z = self.dropout(poids) @ v
        lot, _, longueur, _ = z.shape
        return self.sortie(z.transpose(1, 2).reshape(lot, longueur, self.tetes * self.d_tete))


class CoucheEncodeur(nn.Module):
    def __init__(self, d_model: int, tetes: int, d_ff: int, dropout: float):
        super().__init__()
        self.attention = AttentionMultiTetes(d_model, tetes, dropout)
        self.norme1, self.norme2 = nn.LayerNorm(d_model), nn.LayerNorm(d_model)
        self.ff = nn.Sequential(nn.Linear(d_model, d_ff), nn.ReLU(), nn.Dropout(dropout), nn.Linear(d_ff, d_model))
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.norme1(x + self.dropout(self.attention(x)))
        return self.norme2(x + self.dropout(self.ff(x)))


class TransformerEncodeur(nn.Module):
    """Encodeur seul, codé à la main : projection, position sinusoïdale, couches, dernier jour -> prévision."""

    def __init__(self, n_entrees: int, longueur: int, d_model: int, tetes: int, couches: int, d_ff: int, dropout: float):
        super().__init__()
        self.projection = nn.Linear(n_entrees, d_model)
        position = torch.arange(longueur).unsqueeze(1)
        frequences = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(longueur, d_model)
        pe[:, 0::2] = torch.sin(position * frequences)
        pe[:, 1::2] = torch.cos(position * frequences)
        self.register_buffer("position", pe.unsqueeze(0))
        self.couches = nn.ModuleList(CoucheEncodeur(d_model, tetes, d_ff, dropout) for _ in range(couches))
        self.sortie = nn.Linear(d_model, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.projection(x) + self.position[:, : x.shape[1], :]
        for couche in self.couches:
            z = couche(z)
        return self.sortie(z[:, -1, :]).squeeze(-1)


def perte_mse_tft():
    """Perte MSE pour le TFT de pytorch-forecasting (qui ne fournit que RMSE) : même perte que les autres modèles."""
    from perte_tft import MSE   # import tardif : pytorch-forecasting n'est chargé que pour le TFT

    return MSE()
