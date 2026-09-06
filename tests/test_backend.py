import io
import unittest
from unittest.mock import patch

from PIL import Image

import server
from models.manager import ModelRegistry


def imagem_png(tamanho=(32, 32)):
    buffer = io.BytesIO()
    Image.new("RGB", tamanho, (120, 80, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


class BackendTestCase(unittest.TestCase):
    def setUp(self):
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()

    def upload(self, endpoint, payload, filename="teste.png"):
        return self.client.post(
            endpoint,
            data={"file": (io.BytesIO(payload), filename)},
            content_type="multipart/form-data",
        )

    def test_upload_ausente(self):
        response = self.client.post("/analyze/full")
        self.assertEqual(response.status_code, 400)
        self.assertIn("erro", response.get_json())

    def test_quick_aceita_png_valido(self):
        response = self.upload("/analyze/quick", imagem_png())
        self.assertEqual(response.status_code, 200)
        self.assertIn("categorias", response.get_json())

    def test_full_rejeita_conteudo_invalido(self):
        response = self.upload("/analyze/full", b"nao e uma imagem")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_quick_rejeita_conteudo_invalido(self):
        response = self.upload("/analyze/quick", b"nao e uma imagem")
        self.assertEqual(response.status_code, 400)

    def test_full_rejeita_extensao_incompativel(self):
        response = self.upload("/analyze/full", imagem_png(), "teste.jpg")
        self.assertEqual(response.status_code, 400)

    def test_deep_aceita_imagem_valida(self):
        response = self.upload("/analyze/deep", imagem_png())
        self.assertEqual(response.status_code, 200)
        self.assertIn("forense", response.get_json())

    def test_full_aceita_imagem_valida_sem_probabilidade(self):
        response = self.upload("/analyze/full", imagem_png())
        self.assertEqual(response.status_code, 200)
        dados = response.get_json()
        self.assertIn("decisao", dados)
        self.assertNotIn("probabilidade", str(dados))

    def test_full_rejeita_imagem_pequena(self):
        response = self.upload("/analyze/full", imagem_png((8, 8)))
        self.assertEqual(response.status_code, 400)

    def test_limite_de_bytes(self):
        payload = b"x" * (server.MAX_IMAGE_BYTES + 1)
        response = self.upload("/analyze/full", payload)
        self.assertEqual(response.status_code, 413)

    def test_health_informa_capacidade(self):
        response = self.client.get("/health")
        dados = response.get_json()
        self.assertIn(response.status_code, (200, 503))
        self.assertIn("capacidade_inferencia", dados)
        self.assertIn("modelos_com_falha", dados)

    def test_respostas_tem_headers_de_seguranca(self):
        response = self.client.get("/health")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("Referrer-Policy"), "no-referrer")

    def test_exiftool_falha_nao_interrompe_quick(self):
        with patch("core.metadata.subprocess.run", side_effect=FileNotFoundError()):
            response = self.upload("/analyze/quick", imagem_png())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["exif"]["_exiftool_status"], "indisponivel")

    def test_exiftool_retorno_nao_zero_e_reportado(self):
        class Resultado:
            returncode = 1
            stdout = ""

        with patch("core.metadata.subprocess.run", return_value=Resultado()):
            response = self.upload("/analyze/quick", imagem_png())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["exif"]["_exiftool_status"], "falhou")

    def test_metadados_sensiveis_nao_sao_expostos(self):
        with patch("core.metadata.subprocess.run") as executar:
            executar.return_value.returncode = 0
            executar.return_value.stdout = '[{"GPSLatitude": 10, "SerialNumber": "privado", "Make": "Camera"}]'
            response = self.upload("/analyze/quick", imagem_png())
        dados = response.get_json()["exif"]
        self.assertNotIn("GPSLatitude", dados)
        self.assertNotIn("SerialNumber", dados)

    def test_bancada_sem_modelos_e_indisponivel(self):
        registry = ModelRegistry(server.BASE_DIR)
        registry.models = {}
        with patch.object(registry, "_prepare_image_tensor", return_value=None):
            resultado = registry.classify_bancada(b"imagem", [0.0] * 10)
        self.assertEqual(resultado["total_ativos"], 0)
        self.assertEqual(resultado["classificacao"], "indisponivel")

    def test_bancada_com_um_modelo_e_inconclusiva(self):
        registry = ModelRegistry(server.BASE_DIR)
        registry.models = {1: object()}
        with patch.object(registry, "_prepare_image_tensor", return_value=None):
            with patch.object(registry, "classify_model", return_value={
                "score": 20.0,
                "nivel": "Baixo",
                "score_normalizado": 0.2,
                "logit": -1.4,
                "calibrado": False,
            }):
                resultado = registry.classify_bancada(b"imagem", [0.0] * 10)
        self.assertEqual(resultado["total_ativos"], 1)
        self.assertEqual(resultado["classificacao"], "inconclusivo")

    def test_bancada_com_discordancia_alta_e_inconclusiva(self):
        registry = ModelRegistry(server.BASE_DIR)
        registry.models = {1: object(), 2: object()}

        def classificar(_image, _features, model_id, img_tensor=None):
            if model_id == 1:
                return {"score": 95.0, "nivel": "Alto", "score_normalizado": 0.95, "logit": 3.0, "calibrado": False}
            return {"score": 5.0, "nivel": "Baixo", "score_normalizado": 0.05, "logit": -3.0, "calibrado": False}

        with patch.object(registry, "_prepare_image_tensor", return_value=None):
            with patch.object(registry, "classify_model", side_effect=classificar):
                resultado = registry.classify_bancada(b"imagem", [0.0] * 10)
        self.assertEqual(resultado["discordancia_modelos"], "Alta")
        self.assertEqual(resultado["classificacao"], "inconclusivo")

    def test_registry_app_carrega_selecao_e_pesos_do_ensemble(self):
        registry = ModelRegistry(server.BASE_DIR)
        registry.warmup()
        self.assertEqual(registry.model_ids, [1, 2, 5, 6])
        self.assertEqual(registry.ensemble_weights, {1: 3.0, 2: 2.5, 5: 1.0, 6: 1.0})
        self.assertEqual(registry.usable_model_count(), 4)

    def test_peso_nao_muda_score_individual(self):
        registry = ModelRegistry(server.BASE_DIR)
        registry.models = {1: object()}
        with patch.object(registry, "_prepare_image_tensor", return_value=None):
            with patch.object(registry, "classify_model", return_value={
                "score": 40.0, "nivel": "Medio", "score_normalizado": 0.4,
                "logit": 0.0, "calibrado": False,
            }):
                resultado = registry.classify_bancada(imagem_png(), [0.0] * 10)
        self.assertEqual(resultado["modelos"]["modelo_1"]["score"], 40.0)
        self.assertEqual(resultado["modelos"]["modelo_1"]["peso"], 3.0)
        self.assertIn("somente media final", resultado["peso_escopo"])


if __name__ == "__main__":
    unittest.main()