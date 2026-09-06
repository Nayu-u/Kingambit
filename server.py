import io
import os
import logging
import warnings
import webbrowser
from functools import wraps
from pathlib import Path
from typing import Callable, Any
from flask import Flask, request, jsonify, send_file, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from PIL import Image, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning
from core.metadata import (
    extrair_metadados,
    categorizar_metadados,
    FORMATOS_IMAGEM_SUPORTADOS,
    TIPOS_IMAGEM,
)
from core.engine import ForensicsEngine
from models.manager import ModelRegistry

app = Flask(__name__)
BASE_DIR = Path(__file__).parent.resolve()
logger = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 50 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 1024 * 1024
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)

LINK_FORMULARIO = "https://docs.google.com/forms/d/e/1FAIpQLSfZ0Ii22rdkT3oJKhd5z-GRRfMdxGzuf4rc1LvABdekFj7bfQ/viewform"
MIN_PIXELS = 16 * 16

registry = ModelRegistry(BASE_DIR)
registry.warmup()

engine = ForensicsEngine()

def require_file(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "file" not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado."}), 400

        arquivo = request.files["file"]
        if not arquivo.filename:
            return jsonify({"erro": "Nome de arquivo vazio."}), 400

        if request.content_length and request.content_length > app.config["MAX_CONTENT_LENGTH"]:
            return jsonify({"erro": "O arquivo excede o limite de tamanho permitido."}), 413

        conteudo = arquivo.stream.read(MAX_IMAGE_BYTES + 1)
        if len(conteudo) > MAX_IMAGE_BYTES:
            return jsonify({"erro": "O arquivo excede o limite de tamanho permitido."}), 413
        nome = arquivo.filename
        return f(conteudo, nome, *args, **kwargs)
    return decorated_function

def validar_imagem(conteudo: bytes, nome: str) -> dict[str, Any]:
    try:
        with Image.open(io.BytesIO(conteudo)) as imagem:
            largura, altura = imagem.size
            formato = (imagem.format or "").upper()
            extensao = Path(nome).suffix.lower()
            if formato not in FORMATOS_IMAGEM_SUPORTADOS:
                raise ValueError("O formato real da imagem nao e suportado para analise.")
            if extensao not in TIPOS_IMAGEM:
                raise ValueError("A extensao do arquivo nao e suportada para analise.")
            extensoes_por_formato = {
                "JPEG": {".jpg", ".jpeg"},
                "PNG": {".png"},
                "WEBP": {".webp"},
                "TIFF": {".tif", ".tiff"},
                "BMP": {".bmp"},
            }
            if extensao not in extensoes_por_formato[formato]:
                raise ValueError("A extensao do arquivo nao corresponde ao formato real da imagem.")
            if largura < 16 or altura < 16 or largura * altura < MIN_PIXELS:
                raise ValueError("A imagem e pequena demais para analise.")
            if largura * altura > MAX_IMAGE_PIXELS:
                raise ValueError("A imagem excede o limite de pixels permitido para analise.")
            if getattr(imagem, "n_frames", 1) != 1:
                raise ValueError("Imagens animadas ou com multiplos frames nao sao suportadas.")
            imagem.verify()
            return {"formato": formato, "largura": largura, "altura": altura}
    except ValueError:
        raise
    except (DecompressionBombError, DecompressionBombWarning, UnidentifiedImageError, OSError) as exc:
        raise ValueError("O arquivo enviado nao e uma imagem valida.") from exc

@app.route("/")
def index() -> Any:
    return send_file(BASE_DIR / "public" / "academico.html")

@app.route("/academico")
def academico() -> Any:
    return send_file(BASE_DIR / "public" / "academico.html")

@app.route("/css/<path:filename>")
def servir_css(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "public" / "css", filename)

@app.route("/js/<path:filename>")
def servir_js(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "public" / "js", filename)

@app.route("/assets/<path:filename>")
def servir_asset(filename: str) -> Any:
    return send_from_directory(BASE_DIR / "public" / "assets", filename)

@app.after_request
def adicionar_cabecalhos_resposta(response: Any) -> Any:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response

@app.route("/analyze/quick", methods=["POST"])
@require_file
def analyze_quick(conteudo: bytes, nome: str) -> Any:
    try:
        if Path(nome).suffix.lower() in TIPOS_IMAGEM:
            validar_imagem(conteudo, nome)
        exif = extrair_metadados(conteudo, nome)
        categorias = categorizar_metadados(exif)
        return jsonify({"exif": exif, "categorias": categorias})
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logger.exception("Falha na analise rapida")
        return jsonify({"erro": "Erro inesperado ao analisar o arquivo."}), 500
    finally:
        del conteudo

@app.route("/analyze/deep", methods=["POST"])
@require_file
def analyze_deep(conteudo: bytes, nome: str) -> Any:
    try:
        sufixo = Path(nome).suffix.lower()
        if sufixo not in TIPOS_IMAGEM:
            return jsonify({"erro": "Analise profunda disponivel apenas para imagens."}), 400
        validar_imagem(conteudo, nome)

        exif = extrair_metadados(conteudo, nome)
        categorias = categorizar_metadados(exif)
        ela_png, _, _ = engine.compute_ela(conteudo)
        ela_b64 = __import__("base64").b64encode(ela_png).decode("utf-8")
        forense = engine.analyze_forensics(conteudo)

        return jsonify({
            "exif": exif,
            "categorias": categorias,
            "ela": ela_b64,
            "forense": forense,
        })
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logger.exception("Falha na analise profunda")
        return jsonify({"erro": "Erro inesperado ao analisar a imagem."}), 500
    finally:
        del conteudo

@app.route("/analyze/full", methods=["POST"])
@require_file
def analyze_full(conteudo: bytes, nome: str) -> Any:
    try:
        sufixo = Path(nome).suffix.lower()
        if sufixo not in TIPOS_IMAGEM:
            return jsonify({"erro": "Analise completa disponivel apenas para imagens."}), 400
        validar_imagem(conteudo, nome)

        exif = extrair_metadados(conteudo, nome)
        categorias = categorizar_metadados(exif)
        forense = engine.analyze_forensics(conteudo)
        if not forense:
            raise ValueError("Nao foi possivel decodificar a imagem enviada.")

        features = [
            forense.get("ela_media", 0.0),
            forense.get("ela_desvio", 0.0),
            forense.get("variancia_ruido", 0.0),
            forense.get("fft_simetria", 0.0),
            forense.get("correlacao_rgb", {}).get("rg", 0.0),
            forense.get("correlacao_rgb", {}).get("rb", 0.0),
            forense.get("correlacao_rgb", {}).get("gb", 0.0),
            forense.get("aberracao_cromatica", 0.0),
            forense.get("gradiente_media", 0.0),
            forense.get("gradiente_desvio", 0.0),
        ]

        bancada = registry.classify_bancada(conteudo, features)

        return jsonify({
            "exif": exif,
            "categorias": categorias,
            "ela": forense.get("ela_b64", ""),
            "forense": forense,
            "bancada": bancada,
            "decisao": {
                "score": bancada["media_geral"],
                "nivel": bancada["nivel_geral"],
                "classificacao": bancada["classificacao"],
                "confianca_consenso": bancada["confianca_consenso"],
                "mensagem": bancada["mensagem"],
                "modelos_ativos": bancada["total_ativos"],
                "calibrada": False,
            },
            "explicacao": {
                "metadados": categorias,
                "forense": forense,
            },
            "incerteza": {
                "dispersao_modelos": bancada["dispersao_modelos"],
                "discordancia_modelos": bancada["discordancia_modelos"],
                "confianca_consenso": bancada["confianca_consenso"],
                "calibrada": False,
            },
        })
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logger.exception("Falha na analise completa")
        return jsonify({"erro": "Erro inesperado ao analisar a imagem."}), 500
    finally:
        del conteudo

@app.route("/formulario", methods=["GET"])
def formulario() -> Any:
    return jsonify({"link": LINK_FORMULARIO})

@app.route("/health", methods=["GET"])
def health() -> Any:
    ativos = registry.usable_model_count()
    status = "ok" if ativos == 4 else "degradado"
    return jsonify({
        "status": status,
        "modelos_ativos": ativos,
        "modelos_esperados": 4,
        "dispositivo": str(registry.device),
        "capacidade_inferencia": ativos > 0,
        "modelos_com_falha": registry.load_errors,
    }), 200 if status == "ok" else 503

@app.route("/privacy")
def privacy() -> Any:
    return send_file(BASE_DIR / "public" / "privacy.html")

@app.route("/terms")
def terms() -> Any:
    return send_file(BASE_DIR / "public" / "terms.html")

@app.errorhandler(404)
def pagina_nao_encontrada(error: Any) -> Any:
    return send_file(BASE_DIR / "public" / "404.html"), 404

@app.errorhandler(413)
def requisicao_muito_grande(error: Any) -> Any:
    return jsonify({"erro": "O servidor ou proxy recusou o tamanho do arquivo."}), 413

@app.errorhandler(RequestEntityTooLarge)
def entidade_muito_grande(error: RequestEntityTooLarge) -> Any:
    return jsonify({"erro": "O arquivo excede o limite de tamanho permitido."}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("AUTO_OPEN") == "1":
        webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=False)