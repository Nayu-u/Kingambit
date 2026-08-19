import logging
import gc
from pathlib import Path
from typing import Dict, Any, Optional, List
import io
import torch
import numpy as np
import joblib
from PIL import Image
from models.architecture import ModeloHibrido, TRANSFORMACAO_AVALIACAO

logger = logging.getLogger(__name__)

class ModelRegistry:
    _instance: Optional["ModelRegistry"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "ModelRegistry":
        if not cls._instance:
            cls._instance = super(ModelRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, base_dir: Path) -> None:
        if self._initialized:
            return
        self.base_dir = base_dir
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device.type == "cpu":
            torch.set_num_threads(1)
        self.shared_model = ModeloHibrido().to(self.device)
        self.shared_model.eval()
        self._initialized = True

    def warmup(self) -> None:
        for m_id in range(1, 5):
            m_path = self.base_dir / f"modelo_{m_id}.pth"
            s_path = self.base_dir / f"normalizador_{m_id}.joblib"
            if m_path.exists() and s_path.exists():
                logger.info(f"Modelo {m_id} e normalizador encontrados no disco.")
            else:
                logger.warning(f"Modelo {m_id} ou normalizador ausente.")

    def classify_model(self, image_bytes: bytes, features: List[float], model_id: int) -> Optional[Dict[str, Any]]:
        model_id = int(model_id)
        m_path = self.base_dir / f"modelo_{model_id}.pth"
        s_path = self.base_dir / f"normalizador_{model_id}.joblib"
        if not m_path.exists() or not s_path.exists():
            return None

        scaler = None
        state_dict = None
        features_arr = None
        features_norm = None
        features_tensor = None
        img = None
        img_tensor = None
        output = None
        try:
            scaler = joblib.load(s_path)
            state_dict = torch.load(m_path, map_location=self.device, weights_only=True)
            self.shared_model.load_state_dict(state_dict)

            features_arr = np.array([features], dtype=np.float32)
            features_norm = scaler.transform(features_arr)
            features_tensor = torch.tensor(features_norm, dtype=torch.float32).to(self.device)

            with Image.open(io.BytesIO(image_bytes)) as source:
                source.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
                img = source.convert("RGB")
                img_tensor = TRANSFORMACAO_AVALIACAO(img).unsqueeze(0).to(self.device)

            with torch.inference_mode():
                output = self.shared_model(img_tensor, features_tensor)
                prob = torch.sigmoid(output).item()

            score = round(prob * 100, 2)
            if score >= 70:
                nivel = "Alto"
            elif score >= 40:
                nivel = "Medio"
            else:
                nivel = "Baixo"

            return {
                "score": score,
                "nivel": nivel,
                "probabilidade": round(prob, 4)
            }
        finally:
            del scaler, state_dict, features_arr, features_norm, features_tensor, img, img_tensor, output
            gc.collect()

    def classify_bancada(self, image_bytes: bytes, features: List[float]) -> Dict[str, Any]:
        results = {}
        weighted_sum = 0.0
        weights_sum = 0.0
        active_count = 0

        names = {
            1: "IA Geral",
            2: "IA Principal",
            3: "IA Multicategoria",
            4: "IA Face Detection"
        }

        weights = {
            1: 1,
            2: 6,
            3: 1,
            4: 1
        }

        for m_id in range(1, 5):
            m_path = self.base_dir / f"modelo_{m_id}.pth"
            s_path = self.base_dir / f"normalizador_{m_id}.joblib"
            if m_path.exists() and s_path.exists():
                try:
                    res = self.classify_model(image_bytes, features, m_id)
                    if res is not None:
                        w = weights[m_id]
                        results[f"modelo_{m_id}"] = {
                            "nome": names[m_id],
                            "score": res["score"],
                            "nivel": res["nivel"],
                            "probabilidade": res["probabilidade"],
                            "peso": w
                        }
                        weighted_sum += res["score"] * w
                        weights_sum += w
                        active_count += 1
                except Exception as e:
                    logger.error(f"Erro ao classificar com Modelo {m_id}: {e}")

        if active_count > 0 and weights_sum > 0:
            media_geral = round(weighted_sum / weights_sum, 2)
            if media_geral >= 70:
                nivel_geral = "Alto"
            elif media_geral >= 40:
                nivel_geral = "Medio"
            else:
                nivel_geral = "Baixo"
        else:
            media_geral = 0.0
            nivel_geral = "Indisponivel"

        return {
            "modelos": results,
            "media_geral": media_geral,
            "nivel_geral": nivel_geral,
            "total_ativos": active_count
        }
