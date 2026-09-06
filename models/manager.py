import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import io
import torch
import numpy as np
import joblib
import json
from PIL import Image
from models.architecture import ModeloHibrido, TRANSFORMACAO_AVALIACAO

logger = logging.getLogger(__name__)

class ModelRegistry:
    def __init__(self, base_dir: Path, model_ids: Optional[List[int]] = None) -> None:
        self.base_dir = base_dir
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.device.type == "cpu":
            torch.set_num_threads(1)
        self.models: Dict[int, Tuple[ModeloHibrido, Any]] = {}
        self.model_metadata: Dict[int, Dict[str, Any]] = {}
        self.load_errors: Dict[int, str] = {}
        manifest_path = self.base_dir / "model_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        registry = manifest.get("registry", {})
        self.model_ids = model_ids if model_ids is not None else registry.get("selected_models", [1, 2, 3, 4])
        self.ensemble_weights = {int(key): float(value) for key, value in registry.get("ensemble_weights", {}).items()}

    def warmup(self) -> None:
        self.models.clear()
        self.model_metadata.clear()
        self.load_errors.clear()
        for m_id in self.model_ids:
            m_path = self.base_dir / f"modelo_{m_id}.pth"
            s_path = self.base_dir / f"normalizador_{m_id}.joblib"
            if m_path.exists() and s_path.exists():
                try:
                    model = ModeloHibrido().to(self.device)
                    state_dict = torch.load(m_path, map_location=self.device, weights_only=True)
                    model.load_state_dict(state_dict)
                    model.eval()
                    scaler = joblib.load(s_path)
                    if getattr(scaler, "n_features_in_", None) != 10:
                        raise ValueError("normalizador com numero incorreto de features")
                    scaler_mean = np.asarray(getattr(scaler, "mean_", []), dtype=np.float32)
                    scaler_scale = np.asarray(getattr(scaler, "scale_", []), dtype=np.float32)
                    if (
                        scaler_mean.shape != (10,)
                        or scaler_scale.shape != (10,)
                        or not np.all(np.isfinite(scaler_mean))
                        or not np.all(np.isfinite(scaler_scale))
                        or np.any(scaler_scale <= 0)
                    ):
                        raise ValueError("normalizador sem media valida para 10 features")
                    self.models[m_id] = (model, scaler)
                    self.model_metadata[m_id] = {
                        "peso_hash": hashlib.sha256(m_path.read_bytes()).hexdigest(),
                        "normalizador_hash": hashlib.sha256(s_path.read_bytes()).hexdigest(),
                        "arquitetura": "ModeloHibrido-EfficientNet-B0",
                        "score_calibrado": False,
                    }
                    logger.info("Modelo %s carregado.", m_id)
                except Exception as exc:
                    self.load_errors[m_id] = type(exc).__name__
                    logger.exception("Falha ao carregar o modelo %s.", m_id)
            else:
                self.load_errors[m_id] = "ausente"
                logger.warning("Modelo %s ou normalizador ausente.", m_id)

    def usable_model_count(self) -> int:
        return len(self.models)

    def _prepare_image_tensor(self, image_bytes: bytes) -> torch.Tensor:
        with Image.open(io.BytesIO(image_bytes)) as source:
            source.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            image = source.convert("RGB")
            return TRANSFORMACAO_AVALIACAO(image).unsqueeze(0).to(self.device)

    def classify_model(self, image_bytes: bytes, features: List[float], model_id: int, img_tensor: Optional[torch.Tensor] = None) -> Optional[Dict[str, Any]]:
        model_id = int(model_id)
        model_bundle = self.models.get(model_id)
        if model_bundle is None:
            return None

        model, scaler = model_bundle
        features_arr = np.array([features], dtype=np.float32)
        if features_arr.shape != (1, 10) or not np.all(np.isfinite(features_arr)):
            raise ValueError("features forenses invalidas")
        features_norm = scaler.transform(features_arr)
        if not np.all(np.isfinite(features_norm)):
            raise ValueError("normalizador produziu features invalidas")
        features_tensor = torch.tensor(features_norm, dtype=torch.float32).to(self.device)

        if img_tensor is None:
            img_tensor = self._prepare_image_tensor(image_bytes)

        with torch.inference_mode():
            output = model(img_tensor, features_tensor)
            logit = float(output.item())

        if not np.isfinite(logit):
            raise ValueError("modelo produziu score invalido")

        score = round(float(torch.sigmoid(torch.tensor(logit)).item()) * 100, 2)
        if score >= 70:
            nivel = "Alto"
        elif score >= 40:
            nivel = "Medio"
        else:
            nivel = "Baixo"

        return {
            "score": score,
            "nivel": nivel,
            "score_normalizado": round(score / 100, 4),
            "logit": round(logit, 6),
            "calibrado": False,
        }

    def classify_bancada(self, image_bytes: bytes, features: List[float]) -> Dict[str, Any]:
        results = {}
        weighted_sum = 0.0
        weights_sum = 0.0
        active_count = 0
        scores_normalizados = []
        logits = []

        names = {
            1: "IA Principal",
            2: "IA Geral",
            3: "IA Multicategoria",
            4: "IA Face Detection",
            5: "IA Faces",
            6: "IA Cenarios",
            7: "IA Animais local",
        }

        weights = {m_id: self.ensemble_weights.get(m_id, 1.0) for m_id in self.model_ids}

        img_tensor = self._prepare_image_tensor(image_bytes)

        for m_id in self.models:
            try:
                res = self.classify_model(image_bytes, features, m_id, img_tensor=img_tensor)
                if res is not None:
                    w = weights.get(m_id, 1.0)
                    results[f"modelo_{m_id}"] = {
                        "nome": names.get(m_id, f"Modelo {m_id}"),
                        "ranking_benchmark": m_id,
                        "score": res["score"],
                        "nivel": res["nivel"],
                        "score_normalizado": res["score_normalizado"],
                        "logit": res["logit"],
                        "calibrado": res["calibrado"],
                        "peso": w,
                        "identidade": self.model_metadata.get(m_id, {}),
                    }
                    weighted_sum += res["score"] * w
                    weights_sum += w
                    active_count += 1
                    scores_normalizados.append(res["score_normalizado"])
                    logits.append(res["logit"])
            except Exception:
                logger.exception("Erro ao classificar com o modelo %s.", m_id)

        dispersao = round(float(np.std(scores_normalizados)), 4) if scores_normalizados else None

        if active_count > 0 and weights_sum > 0:
            media_geral = round(weighted_sum / weights_sum, 2)
            modelos_altos = sum(1 for score_normalizado in scores_normalizados if score_normalizado >= 0.7)
            if media_geral >= 70 and modelos_altos >= 2 and dispersao is not None and dispersao < 0.2:
                nivel_geral = "Alto"
            elif media_geral >= 40:
                nivel_geral = "Medio"
            else:
                nivel_geral = "Baixo"
        else:
            media_geral = 0.0
            nivel_geral = "Indisponivel"

        discordancia = "Indisponivel"
        if dispersao is not None:
            if dispersao >= 0.2:
                discordancia = "Alta"
            elif dispersao >= 0.1:
                discordancia = "Media"
            else:
                discordancia = "Baixa"

        if active_count == 0:
            classificacao = "indisponivel"
            confianca_consenso = "Indisponivel"
            mensagem = "Nenhum modelo disponivel para produzir uma avaliacao."
        elif active_count < 2 or dispersao is None or dispersao >= 0.2:
            classificacao = "inconclusivo"
            confianca_consenso = "Baixa"
            mensagem = "Os modelos nao apresentaram concordancia suficiente para uma conclusao forte."
        elif nivel_geral == "Alto":
            classificacao = "suspeita_alta"
            confianca_consenso = "Media"
            mensagem = "A bancada apresentou concordancia para um resultado de risco elevado."
        elif nivel_geral == "Medio":
            classificacao = "indicios"
            confianca_consenso = "Media"
            mensagem = "Foram encontrados indicios que exigem avaliacao complementar."
        else:
            classificacao = "baixo_indicio"
            confianca_consenso = "Media"
            mensagem = "A bancada nao encontrou indicios fortes, mas o resultado nao e uma prova de autenticidade."

        return {
            "modelos": results,
            "media_geral": media_geral,
            "nivel_geral": nivel_geral,
            "total_ativos": active_count,
            "modelos_com_falha": self.load_errors,
            "media_logits": round(float(np.mean(logits)), 6) if logits else None,
            "peso_escopo": "somente media final do ensemble; nao altera score individual, treino, avaliacao, ranking ou calibracao",
            "score_calibrado": False,
            "dispersao_modelos": dispersao,
            "discordancia_modelos": discordancia,
            "classificacao": classificacao,
            "confianca_consenso": confianca_consenso,
            "mensagem": mensagem
        }

