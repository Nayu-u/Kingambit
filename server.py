import io
import os
import gc
import webbrowser
from functools import wraps
from pathlib import Path
from typing import Callable, Any
from flask import Flask, request, jsonify, send_file, send_from_directory
import pandas as pd
from core.metadata import extrair_metadados, categorizar_metadados, TIPOS_IMAGEM
from core.engine import ForensicsEngine
from models.manager import ModelRegistry

app = Flask(__name__)
BASE_DIR = Path(__file__).parent.resolve()

LINK_FORMULARIO = "https://docs.google.com/forms/d/e/1FAIpQLSfZ0Ii22rdkT3oJKhd5z-GRRfMdxGzuf4rc1LvABdekFj7bfQ/viewform"
CAMINHO_PLANILHA = BASE_DIR / "planilha.xlsx"

registry = ModelRegistry(BASE_DIR)
registry.warmup()

engine = ForensicsEngine()

MAX_CONTENT_LENGTH = 10 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

def require_file(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "file" not in request.files:
            return jsonify({"erro": "Nenhum arquivo enviado."}), 400

        arquivo = request.files["file"]
        if not arquivo.filename:
            return jsonify({"erro": "Nome de arquivo vazio."}), 400

        conteudo = arquivo.read()
        nome = arquivo.filename
        return f(conteudo, nome, *args, **kwargs)
    return decorated_function

def cleanup_memory():
    gc.collect()

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
    caminho_raiz = BASE_DIR / filename
    if caminho_raiz.exists() and caminho_raiz.is_file():
        return send_file(caminho_raiz)
    caminho_public = BASE_DIR / "public" / filename
    if caminho_public.exists() and caminho_public.is_file():
        return send_file(caminho_public)
    return "", 404

@app.route("/analyze/quick", methods=["POST"])
@require_file
def analyze_quick(conteudo: bytes, nome: str) -> Any:
    try:
        exif = extrair_metadados(conteudo, nome)
        categorias = categorizar_metadados(exif)
        return jsonify({"exif": exif, "categorias": categorias})
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": f"Erro inesperado: {e}"}), 500
    finally:
        del conteudo
        cleanup_memory()

@app.route("/analyze/deep", methods=["POST"])
@require_file
def analyze_deep(conteudo: bytes, nome: str) -> Any:
    try:
        sufixo = Path(nome).suffix.lower()
        if sufixo not in TIPOS_IMAGEM:
            return jsonify({"erro": "Analise profunda disponivel apenas para imagens."}), 400

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
        return jsonify({"erro": f"Erro inesperado: {e}"}), 500
    finally:
        del conteudo
        cleanup_memory()

@app.route("/analyze/full", methods=["POST"])
@require_file
def analyze_full(conteudo: bytes, nome: str) -> Any:
    try:
        sufixo = Path(nome).suffix.lower()
        if sufixo not in TIPOS_IMAGEM:
            return jsonify({"erro": "Analise completa disponivel apenas para imagens."}), 400

        exif = extrair_metadados(conteudo, nome)
        categorias = categorizar_metadados(exif)
        forense = engine.analyze_forensics(conteudo)

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
            "bancada": bancada
        })
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        return jsonify({"erro": f"Erro inesperado: {e}"}), 500
    finally:
        del conteudo
        cleanup_memory()

@app.route("/formulario", methods=["GET"])
def formulario() -> Any:
    return jsonify({"link": LINK_FORMULARIO})

@app.route("/respostas", methods=["GET"])
def respostas() -> Any:
    try:
        if not CAMINHO_PLANILHA.exists():
            return jsonify({"erro": "Nenhuma planilha encontrada."}), 404

        df = pd.read_excel(CAMINHO_PLANILHA)
        colunas = list(df.columns)
        dados = df.to_dict(orient="records")

        return jsonify({
            "colunas": colunas,
            "dados": dados,
            "total": len(dados),
        })
    except Exception as e:
        return jsonify({"erro": f"Erro ao ler planilha: {e}"}), 500

@app.route("/privacy")
def privacy() -> Any:
    return send_file(BASE_DIR / "public" / "privacy.html")

@app.route("/terms")
def terms() -> Any:
    return send_file(BASE_DIR / "public" / "terms.html")

@app.errorhandler(404)
def pagina_nao_encontrada(error: Any) -> Any:
    return send_file(BASE_DIR / "public" / "404.html"), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("AUTO_OPEN") == "1":
        webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=False)