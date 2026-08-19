from pathlib import Path
from typing import Tuple, Any
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from torchvision import transforms, models
from PIL import Image

COLUNAS_FEATURES = [
    "ela_media",
    "ela_desvio",
    "variancia_ruido",
    "fft_simetria",
    "corr_rg",
    "corr_rb",
    "corr_gb",
    "aberracao_cromatica",
    "gradiente_media",
    "gradiente_desvio",
]

NUM_FEATURES_FORENSES = len(COLUNAS_FEATURES)
TAMANHO_IMAGEM = 224

TRANSFORMACAO_TREINO = transforms.Compose([
    transforms.Resize((TAMANHO_IMAGEM, TAMANHO_IMAGEM)),
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(15),
    transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.1),
    transforms.RandomGrayscale(p=0.05),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

TRANSFORMACAO_AVALIACAO = transforms.Compose([
    transforms.Resize((TAMANHO_IMAGEM, TAMANHO_IMAGEM)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

class DatasetHibrido(Dataset):
    def __init__(self, conjunto: str, transformacao: Any, dataset_id: int, normalizador: Any = None) -> None:
        self.transformacao = transformacao
        self.normalizador = normalizador
        self.dataset_id = int(dataset_id)
        self.projeto_dir = Path(__file__).parent.parent.resolve()

        folder_mapping = {
            1: ("archive", "_1"),
            2: ("archive (1)", "_2"),
            3: ("archive (2)", "_3"),
            4: ("archive (3)", "_4")
        }

        if self.dataset_id not in folder_mapping:
            raise ValueError(f"ID de dataset invalido: {dataset_id}")

        folder_name, suffix = folder_mapping[self.dataset_id]
        self.base_features = self.projeto_dir / folder_name

        split_map = {
            "train": "train",
            "valid": "valid",
            "validation": "valid",
            "test": "test"
        }
        split_key = split_map.get(conjunto, conjunto)
        csv_path = self.base_features / f"features_{split_key}{suffix}.csv"

        if not csv_path.exists():
            raise FileNotFoundError(f"Arquivo CSV nao encontrado: {csv_path}")

        self.df = pd.read_csv(csv_path)
        self.mapa_features = {}
        for _, linha in self.df.iterrows():
            rel_path = linha["arquivo"]
            valores = [float(linha[col]) for col in COLUNAS_FEATURES]
            self.mapa_features[rel_path] = np.array(valores, dtype=np.float32)

        self.amostras = []
        for _, linha in self.df.iterrows():
            rel_path = linha["arquivo"]
            rotulo = int(linha["rotulo"])
            caminho = self.base_features / rel_path
            if caminho.exists() and rel_path in self.mapa_features:
                self.amostras.append((caminho, rotulo, rel_path))

    def __len__(self) -> int:
        return len(self.amostras)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        caminho, rotulo, rel_path = self.amostras[idx]
        imagem = Image.open(caminho).convert("RGB")
        imagem = self.transformacao(imagem)
        features = self.mapa_features[rel_path].copy()
        
        if self.normalizador is not None:
            features = self.normalizador.transform(features.reshape(1, -1)).flatten()
            
        return (
            imagem,
            torch.tensor(features, dtype=torch.float32),
            torch.tensor(rotulo, dtype=torch.float32)
        )

class ModeloHibrido(nn.Module):
    def __init__(self, pretrained: bool = False) -> None:
        super().__init__()
        if pretrained:
            self.cnn = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
        else:
            self.cnn = models.efficientnet_b0(weights=None)
        
        num_features_cnn = self.cnn.classifier[1].in_features
        self.cnn.classifier = nn.Identity()

        self.camada_forense = nn.Sequential(
            nn.Linear(NUM_FEATURES_FORENSES, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
        )

        tamanho_fusao = num_features_cnn + 32
        self.classificador = nn.Sequential(
            nn.Linear(tamanho_fusao, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(64, 1),
        )

    def forward(self, imagem: torch.Tensor, features_forenses: torch.Tensor) -> torch.Tensor:
        saida_cnn = self.cnn(imagem)
        saida_forense = self.camada_forense(features_forenses)
        fusao = torch.cat([saida_cnn, saida_forense], dim=1)
        return self.classificador(fusao).squeeze(1)

