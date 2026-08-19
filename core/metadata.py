import os
import tempfile
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List

TIPOS_IMAGEM = frozenset({
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".tiff", ".tif", ".gif", ".bmp", ".raw",
})

TIPOS_VIDEO = frozenset({
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v",
})

CAMPOS_BINARIOS = frozenset({
    "item 0", "item 1", "item 2", "item 3",
    "item 1 sig tst 2 tst tokens val",
    "item 1r vals ocsp vals",
    "item 1 pad", "item 1 pad 2",
    "created assertions hash",
    "hash", "pad",
})

CAMPOS_IGNORADOS = frozenset({"sourcefile", "exiftoolversion"})

CAMPOS_IA = {
    "software": [
        "stable diffusion", "midjourney", "dall-e", "dalle",
        "novelai", "comfyui", "automatic1111", "invoke",
        "diffusers", "dreamstudio", "leonardo", "playground",
        "adobe firefly", "firefly", "bing image creator",
        "copilot", "chatgpt", "gpt", "gemini", "ideogram",
    ],
    "chaves": [
        "software", "generator", "creator", "creatortool",
        "historysoftwareagent", "comment", "usercomment",
        "description", "imagedescription", "xmptoolkit",
        "model", "source", "aimodel", "prompt",
        "negativeprompt", "sampler", "cfgscale", "steps",
        "seed", "denoisingstrength", "clipskip",
        "aigeneratedcontent", "aiassisted",
    ],
}

CAMPOS_CAMERA = [
    "make", "model", "lensmodel", "lensmake", "lensinfo",
    "focallength", "focallengthin35mmformat",
    "fnumber", "aperture", "aperturevalue",
    "exposuretime", "shutterspeedvalue", "shutterspeed",
    "iso", "isospeedratings", "photographicsensitivity",
    "flash", "flashfired", "flashmode",
    "whitebalance", "meteringmode", "exposuremode",
    "exposureprogram", "exposurecompensation",
    "scenecapturetype", "digitalzoomratio",
    "gaincontrol", "contrast", "saturation", "sharpness",
    "subjectdistance", "subjectdistancerange",
    "serialnumber", "bodyserialnumber", "lensserialnumber",
    "internalserialnumber",
]

CAMPOS_ARQUIVO = [
    "filename", "directory", "filesize", "filemodifydate",
    "fileaccessdate", "filecreatedate", "filetype",
    "filetypeextension", "mimetype", "imagewidth",
    "imageheight", "imagesize", "megapixels",
    "bitdepth", "colorspace", "colortype",
    "compression", "quality", "encoding",
    "xresolution", "yresolution", "resolutionunit",
    "datetimeoriginal", "createdate", "modifydate",
    "offsettime", "offsettimeoriginal",
    "gpslatitude", "gpslongitude", "gpsaltitude",
    "gpsposition",
]

def detectar_tipo(nome: str) -> str:
    ext = Path(nome).suffix.lower()
    if ext in TIPOS_IMAGEM:
        return "imagem"
    if ext in TIPOS_VIDEO:
        return "video"
    raise ValueError("Tipo nao suportado")

def normalizar_metadados(dados: Dict[str, Any]) -> Dict[str, Any]:
    resultado = {}
    for chave, valor in dados.items():
        chave_limpa = chave.split(":")[-1]
        if chave_limpa.lower() in CAMPOS_IGNORADOS:
            continue
        if chave_limpa.lower() in CAMPOS_BINARIOS:
            continue
        if isinstance(valor, str) and "(Binary data" in valor:
            continue
        resultado[chave_limpa] = valor
    return resultado

def extrair_metadados(conteudo: bytes, nome_arquivo: str) -> Dict[str, Any]:
    tipo = detectar_tipo(nome_arquivo)
    sufixo = Path(nome_arquivo).suffix
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
        tmp.write(conteudo)
        caminho_tmp = tmp.name

    meta = {}
    try:
        res = subprocess.run(
            ["exiftool", "-j", caminho_tmp],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0:
            dados_brutos = json.loads(res.stdout)
            if dados_brutos:
                meta = normalizar_metadados(dados_brutos[0])
    except Exception:
        pass
    finally:
        try:
            os.unlink(caminho_tmp)
        except OSError:
            pass

    meta["_nome_arquivo"] = nome_arquivo
    meta["_tipo_arquivo"] = tipo
    meta["_tamanho_kb"] = round(len(conteudo) / 1024, 2)
    return meta

def categorizar_metadados(meta: Dict[str, Any]) -> Dict[str, Any]:
    ia = {}
    camera = {}
    arquivo = {}
    outros = {}
    indicios_ia: List[Dict[str, str]] = []

    for chave, valor in meta.items():
        if chave.startswith("_"):
            arquivo[chave] = valor
            continue

        chave_lower = chave.lower().replace(" ", "").replace("_", "")
        encontrado = False

        for campo_ia in CAMPOS_IA["chaves"]:
            if campo_ia in chave_lower:
                ia[chave] = valor
                encontrado = True
                if isinstance(valor, str):
                    valor_lower = valor.lower()
                    for termo in CAMPOS_IA["software"]:
                        if termo in valor_lower:
                            indicios_ia.append({
                                "campo": chave,
                                "valor": valor,
                                "motivo": f"Contem referencia a ferramenta de IA: {termo}",
                            })
                            break
                    palavras_suspeitas = [
                        "generated", "artificial", "synthetic", "ai",
                        "neural", "diffusion", "gan",
                    ]
                    for palavra in palavras_suspeitas:
                        if palavra in valor_lower:
                            indicios_ia.append({
                                "campo": chave,
                                "valor": valor,
                                "motivo": f"Contem termo associado a geracao artificial: {palavra}",
                            })
                            break
                break

        if encontrado:
            continue

        for campo_cam in CAMPOS_CAMERA:
            if campo_cam in chave_lower:
                camera[chave] = valor
                encontrado = True
                break

        if encontrado:
            continue

        for campo_arq in CAMPOS_ARQUIVO:
            if campo_arq in chave_lower:
                arquivo[chave] = valor
                encontrado = True
                break

        if encontrado:
            continue

        outros[chave] = valor

    if not ia and not camera.get("Make") and not camera.get("Model"):
        indicios_ia.append({
            "campo": "Geral",
            "valor": "Ausente",
            "motivo": "Nenhum metadado de IA ou camera encontrado - metadados podem ter sido removidos",
        })

    return {
        "ia": ia,
        "indicios_ia": indicios_ia,
        "camera": camera,
        "arquivo": arquivo,
        "outros": outros,
    }
