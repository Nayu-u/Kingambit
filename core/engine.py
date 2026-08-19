import io
import base64
import gc
from typing import Tuple, Dict, Any, List, Optional
import cv2
import numpy as np
from PIL import Image, ImageChops

class ForensicsEngine:
    MAX_PIXELS = 1920 * 1080

    def __init__(self, ela_quality: int = 90, ela_amplification: int = 15) -> None:
        self.ela_quality = ela_quality
        self.ela_amplification = ela_amplification

    def _load_image(self, image_bytes: bytes) -> Image.Image:
        with Image.open(io.BytesIO(image_bytes)) as source:
            source.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            return source.convert("RGB")

    def compute_ela(self, image_bytes: bytes) -> Tuple[bytes, float, float]:
        original = None
        compressed_buffer = None
        compressed = None
        diff = None
        arr = None
        amplified = None
        output_buffer = None
        try:
            original = self._load_image(image_bytes)
            compressed_buffer = io.BytesIO()
            original.save(compressed_buffer, format="JPEG", quality=self.ela_quality)
            compressed_buffer.seek(0)
            with Image.open(compressed_buffer) as compressed_source:
                compressed = compressed_source.convert("RGB")
                diff = ImageChops.difference(original, compressed)
                arr = np.asarray(diff, dtype=np.float32)
                amplified = np.clip(arr * self.ela_amplification, 0, 255).astype(np.uint8)
                output_buffer = io.BytesIO()
                Image.fromarray(amplified).save(output_buffer, format="PNG")
                return output_buffer.getvalue(), float(np.mean(arr)), float(np.std(arr))
        finally:
            del original, compressed_buffer, compressed, diff, arr, amplified, output_buffer
            gc.collect()

    def extract_srm_noise_variance(self, gray_image: np.ndarray) -> float:
        srm_kernel = np.array([[-1, 2, -1], [2, -4, 2], [-1, 2, -1]], dtype=np.float32) / 4.0
        residual = cv2.filter2D(gray_image, -1, srm_kernel)
        
        block_size = 16
        h, w = residual.shape
        n_rows = h // block_size
        n_cols = w // block_size
        
        if n_rows == 0 or n_cols == 0:
            return 0.0
            
        variances = []
        for r in range(n_rows):
            for c in range(n_cols):
                rs = r * block_size
                cs = c * block_size
                block = residual[rs : rs + block_size, cs : cs + block_size]
                variances.append(float(np.var(block)))
                
        return float(np.mean(variances))

    def compute_fft_symmetry(self, gray_image: np.ndarray) -> Tuple[bytes, float]:
        f_transform = np.fft.fft2(gray_image.astype(np.float32))
        f_shifted = np.fft.fftshift(f_transform)
        magnitude = np.log1p(np.abs(f_shifted))
        
        magnitude_norm = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        magnitude_color = cv2.applyColorMap(magnitude_norm, cv2.COLORMAP_INFERNO)
        _, buffer_fft = cv2.imencode(".png", magnitude_color)
        fft_b64 = base64.b64encode(buffer_fft).decode("utf-8")
        
        h, w = magnitude.shape
        half_h = h // 2
        top_half = magnitude[:half_h, :]
        bottom_half_flipped = np.flipud(magnitude[half_h:, :])
        min_dim = min(top_half.shape[0], bottom_half_flipped.shape[0])
        
        diff = np.abs(top_half[:min_dim] - bottom_half_flipped[:min_dim])
        symmetry = float(1.0 - (np.mean(diff) / (np.max(magnitude) + 1e-9)))
        
        return fft_b64.encode("utf-8"), symmetry

    def compute_rgb_correlation(self, bgr_image: np.ndarray) -> Dict[str, float]:
        b, g, r = cv2.split(bgr_image.astype(np.float32))
        
        def corr(channel_a: np.ndarray, channel_b: np.ndarray) -> float:
            flat_a = channel_a.flatten()
            flat_b = channel_b.flatten()
            if np.std(flat_a) < 1e-9 or np.std(flat_b) < 1e-9:
                return 1.0
            return float(np.corrcoef(flat_a, flat_b)[0, 1])

        return {
            "rg": round(corr(r, g), 4),
            "rb": round(corr(r, b), 4),
            "gb": round(corr(g, b), 4),
        }

    def compute_chromatic_aberration(self, bgr_image: np.ndarray) -> float:
        smoothed = cv2.GaussianBlur(bgr_image, (3, 3), 0)
        b, g, r = cv2.split(smoothed)
        
        edges_r = cv2.Canny(r, 30, 90)
        edges_g = cv2.Canny(g, 30, 90)
        edges_b = cv2.Canny(b, 30, 90)
        
        mask = (edges_r > 0) | (edges_g > 0) | (edges_b > 0)
        total_pixels = float(np.count_nonzero(mask)) + 1e-9
        
        diff_rg = np.count_nonzero(cv2.bitwise_xor(edges_r, edges_g) & mask)
        diff_rb = np.count_nonzero(cv2.bitwise_xor(edges_r, edges_b) & mask)
        diff_gb = np.count_nonzero(cv2.bitwise_xor(edges_g, edges_b) & mask)
        
        misalignment = float(diff_rg + diff_rb + diff_gb)
        return misalignment / (2.0 * total_pixels)

    def compute_gradient_features(self, bgr_image: np.ndarray) -> Tuple[bytes, float, float]:
        yuv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2YUV)
        y, _, _ = cv2.split(yuv)
        
        sobel_x = cv2.Sobel(y, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(y, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
        
        grad_norm = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        _, buffer_grad = cv2.imencode(".png", grad_norm)
        grad_b64 = base64.b64encode(buffer_grad).decode("utf-8")
        
        return grad_b64.encode("utf-8"), float(np.mean(magnitude)), float(np.std(magnitude))

    def extract_vector_from_bytes(self, image_bytes: bytes) -> Optional[List[float]]:
        arr_np = None
        img = None
        img_resized = None
        resized_bytes = None
        gray_resized = None
        try:
            arr_np = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(arr_np, cv2.IMREAD_COLOR)
            if img is None:
                return None
                
            img_resized = cv2.resize(img, (256, 256))
            resized_bytes = cv2.imencode(".jpg", img_resized)[1].tobytes()
            
            gray_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            _, ela_m, ela_s = self.compute_ela(resized_bytes)
            var_noise = self.extract_srm_noise_variance(gray_resized)
            _, fft_sim = self.compute_fft_symmetry(gray_resized)
            corr_rgb = self.compute_rgb_correlation(img_resized)
            aber = self.compute_chromatic_aberration(img_resized)
            _, grad_m, grad_s = self.compute_gradient_features(img_resized)
            
            return [
                ela_m, ela_s, var_noise, fft_sim,
                corr_rgb["rg"], corr_rgb["rb"], corr_rgb["gb"],
                aber, grad_m, grad_s
            ]
        except Exception:
            return None
        finally:
            del arr_np, img, img_resized, resized_bytes, gray_resized
            gc.collect()

    def analyze_forensics(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            return self._analyze_forensics(image_bytes)
        finally:
            gc.collect()

    def _analyze_forensics(self, image_bytes: bytes) -> Dict[str, Any]:
        arr_np = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr_np, cv2.IMREAD_COLOR)
        if img is None:
            return {}

        height, width = img.shape[:2]
        if width * height > self.MAX_PIXELS:
            scale = (self.MAX_PIXELS / float(width * height)) ** 0.5
            img = cv2.resize(img, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        grad_b64_bytes, _, _ = self.compute_gradient_features(img)
        
        srm_kernel = np.array([[-1, 2, -1], [2, -4, 2], [-1, 2, -1]], dtype=np.float32) / 4.0
        residual_srm = cv2.filter2D(gray, -1, srm_kernel)
        block_size = 16
        h, w = residual_srm.shape
        n_rows = h // block_size
        n_cols = w // block_size
        
        heatmap = np.zeros((n_rows, n_cols), dtype=np.float32)
        for r in range(n_rows):
            for c in range(n_cols):
                rs = r * block_size
                cs = c * block_size
                block = residual_srm[rs : rs + block_size, cs : cs + block_size]
                heatmap[r, c] = float(np.var(block))
                
        heatmap_norm = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
        heatmap_resized = cv2.resize(heatmap_color, (w, h), interpolation=cv2.INTER_NEAREST)
        _, buffer_heatmap = cv2.imencode(".png", heatmap_resized)
        noise_b64 = base64.b64encode(buffer_heatmap).decode("utf-8")
        
        fft_b64_bytes, _ = self.compute_fft_symmetry(gray)
        ela_png_bytes, _, _ = self.compute_ela(image_bytes)
        ela_b64 = base64.b64encode(ela_png_bytes).decode("utf-8")
        
        img_256 = cv2.resize(img, (256, 256))
        resized_bytes = cv2.imencode(".jpg", img_256)[1].tobytes()
        gray_256 = cv2.cvtColor(img_256, cv2.COLOR_BGR2GRAY)
        
        _, ela_m_256, ela_s_256 = self.compute_ela(resized_bytes)
        var_noise_256 = self.extract_srm_noise_variance(gray_256)
        _, fft_sim_256 = self.compute_fft_symmetry(gray_256)
        corr_rgb_256 = self.compute_rgb_correlation(img_256)
        aber_256 = self.compute_chromatic_aberration(img_256)
        _, grad_m_256, grad_s_256 = self.compute_gradient_features(img_256)
        
        ela_m_val = round(ela_m_256, 4)
        ela_s_val = round(ela_s_256, 4)
        var_noise_val = round(var_noise_256, 4)
        fft_sim_val = round(fft_sim_256, 4)
        aber_val = round(aber_256, 4)
        grad_m_val = round(grad_m_256, 4)
        grad_s_val = round(grad_s_256, 4)
        
        interpretations = self._interpret_metrics(
            ela_m_val, ela_s_val, var_noise_val, fft_sim_val,
            corr_rgb_256, aber_val, grad_m_val, grad_s_val
        )
        
        return {
            "mapa_gradiente_b64": grad_b64_bytes.decode("utf-8"),
            "mapa_ruido_b64": noise_b64,
            "variancia_ruido": var_noise_val,
            "fft_mapa_b64": fft_b64_bytes.decode("utf-8"),
            "fft_simetria": fft_sim_val,
            "correlacao_rgb": corr_rgb_256,
            "aberracao_cromatica": aber_val,
            "gradiente_media": grad_m_val,
            "gradiente_desvio": grad_s_val,
            "ela_media": ela_m_val,
            "ela_desvio": ela_s_val,
            "ela_b64": ela_b64,
            "interpretacao": interpretations
        }

    def _interpret_metrics(
        self, ela_media: float, ela_desvio: float, variancia_ruido: float,
        fft_simetria: float, corr_rgb: Dict[str, float], aberracao: float,
        grad_media: float, grad_desvio: float
    ) -> Dict[str, Any]:
        conclusions = []
        
        if ela_media < 15:
            conclusions.append({
                "area": "ELA",
                "indicador": "Baixa variacao ELA",
                "valor": ela_media,
                "interpretacao": "A imagem apresenta niveis de compressao muito uniformes. Isso pode indicar que a imagem foi gerada sinteticamente ou recomprimida multiplas vezes.",
                "severidade": "alta"
            })
        elif ela_media < 30:
            conclusions.append({
                "area": "ELA",
                "indicador": "Variacao ELA moderada",
                "valor": ela_media,
                "interpretacao": "A imagem apresenta variacao moderada nos niveis de compressao. Consistente com imagens naturais que passaram por algum processamento.",
                "severidade": "media"
            })
        else:
            conclusions.append({
                "area": "ELA",
                "indicador": "Variacao ELA elevada",
                "valor": ela_media,
                "interpretacao": "A imagem apresenta variacao significativa nos niveis de compressao. Pode indicar regioes editadas ou colagem de diferentes fontes.",
                "severidade": "alta"
            })
            
        if ela_desvio < 10:
            conclusions.append({
                "area": "ELA",
                "indicador": "Desvio ELA baixo",
                "valor": ela_desvio,
                "interpretacao": "A distribuicao do erro de compressao e muito homogenea. Comum em imagens geradas por IA, que nao passam por compressao JPEG real.",
                "severidade": "alta"
            })
            
        if variancia_ruido < 3:
            conclusions.append({
                "area": "Ruido",
                "indicador": "Ruido muito uniforme",
                "valor": variancia_ruido,
                "interpretacao": "O ruido da imagem e extremamente uniforme. Imagens de cameras reais possuem ruido com variacao natural. Forte indicacao de geracao artificial.",
                "severidade": "alta"
            })
        elif variancia_ruido < 7:
            conclusions.append({
                "area": "Ruido",
                "indicador": "Ruido pouco variado",
                "valor": variancia_ruido,
                "interpretacao": "O ruido apresenta pouca variacao entre regioes. Pode indicar suavizacao excessiva ou geracao artificial.",
                "severidade": "media"
            })
        elif variancia_ruido > 80:
            conclusions.append({
                "area": "Ruido",
                "indicador": "Ruido excessivo",
                "valor": variancia_ruido,
                "interpretacao": "O ruido apresenta variacao muito alta entre regioes. Pode indicar colagem de diferentes fontes com caracteristicas de ruido distintas.",
                "severidade": "media"
            })
        else:
            conclusions.append({
                "area": "Ruido",
                "indicador": "Ruido dentro do esperado",
                "valor": variancia_ruido,
                "interpretacao": "A distribuicao de ruido e consistente com uma imagem capturada por camera real.",
                "severidade": "baixa"
            })
            
        if fft_simetria > 0.98:
            conclusions.append({
                "area": "FFT",
                "indicador": "Simetria espectral muito alta",
                "valor": fft_simetria,
                "interpretacao": "O espectro de frequencias e quase perfeitamente simetrico. Isso e raro em fotografias naturais e comum em imagens geradas por redes neurais.",
                "severidade": "alta"
            })
        elif fft_simetria > 0.95:
            conclusions.append({
                "area": "FFT",
                "indicador": "Simetria espectral elevada",
                "valor": fft_simetria,
                "interpretacao": "O espectro de frequencias apresenta simetria acima do comum. Merece atencao.",
                "severidade": "media"
            })
        else:
            conclusions.append({
                "area": "FFT",
                "indicador": "Simetria espectral normal",
                "valor": fft_simetria,
                "interpretacao": "O espectro de frequencias apresenta assimetria natural, consistente com fotografias reais.",
                "severidade": "baixa"
            })
            
        rg = abs(corr_rgb.get("rg", 0.0))
        rb = abs(corr_rgb.get("rb", 0.0))
        gb = abs(corr_rgb.get("gb", 0.0))
        mean_corr = (rg + rb + gb) / 3.0
        
        if mean_corr > 0.98:
            conclusions.append({
                "area": "Correlacao RGB",
                "indicador": "Correlacao entre canais extremamente alta",
                "valor": round(mean_corr, 4),
                "interpretacao": "Os canais de cor estao quase identicos. Isso pode indicar uma imagem quase monocromatica ou geracao artificial com pouca variacao de cor.",
                "severidade": "alta"
            })
        elif mean_corr > 0.92:
            conclusions.append({
                "area": "Correlacao RGB",
                "indicador": "Correlacao entre canais elevada",
                "valor": round(mean_corr, 4),
                "interpretacao": "Os canais de cor apresentam correlacao acima do comum. Pode indicar processamento artificial.",
                "severidade": "media"
            })
        else:
            conclusions.append({
                "area": "Correlacao RGB",
                "indicador": "Correlacao entre canais normal",
                "valor": round(mean_corr, 4),
                "interpretacao": "A relacao entre os canais de cor e consistente com uma fotografia natural.",
                "severidade": "baixa"
            })
            
        if aberracao < 0.03:
            conclusions.append({
                "area": "Aberracao Cromatica",
                "indicador": "Aberracao cromatica ausente",
                "valor": aberracao,
                "interpretacao": "A imagem nao apresenta aberracao cromatica. Cameras reais produzem algum grau de aberracao devido as propriedades opticas das lentes. A ausencia total e comum em imagens geradas por IA.",
                "severidade": "alta"
            })
        elif aberracao < 0.08:
            conclusions.append({
                "area": "Aberracao Cromatica",
                "indicador": "Aberracao cromatica baixa",
                "valor": aberracao,
                "interpretacao": "A imagem apresenta pouca aberracao cromatica. Pode ser uma lente de alta qualidade ou indicar geracao artificial.",
                "severidade": "media"
            })
        elif aberracao > 0.20:
            conclusions.append({
                "area": "Aberracao Cromatica",
                "indicador": "Aberracao cromatica excessiva",
                "valor": aberracao,
                "interpretacao": "A imagem apresenta aberracao cromatica acima do normal. Pode indicar manipulacao nas bordas ou uso de lentes de baixa qualidade.",
                "severidade": "media"
            })
        else:
            conclusions.append({
                "area": "Aberracao Cromatica",
                "indicador": "Aberracao cromatica dentro do esperado",
                "valor": aberracao,
                "interpretacao": "O nivel de aberracao cromatica e consistente com uma fotografia capturada por camera real.",
                "severidade": "baixa"
            })
            
        if grad_media < 5:
            conclusions.append({
                "area": "Gradiente",
                "indicador": "Transicoes muito suaves",
                "valor": grad_media,
                "interpretacao": "A imagem apresenta transicoes extremamente suaves entre regioes. Pode indicar suavizacao artificial ou geracao por IA.",
                "severidade": "media"
            })
        elif grad_desvio < 8:
            conclusions.append({
                "area": "Gradiente",
                "indicador": "Variacao de bordas baixa",
                "valor": grad_desvio,
                "interpretacao": "A variacao nas transicoes e baixa, indicando uniformidade incomum. Fotografias naturais tendem a ter maior variacao.",
                "severidade": "media"
            })
        else:
            conclusions.append({
                "area": "Gradiente",
                "indicador": "Transicoes dentro do esperado",
                "valor": grad_media,
                "interpretacao": "O padrao de transicoes e bordas e consistente com uma fotografia natural.",
                "severidade": "baixa"
            })
            
        high_severity_count = sum(1 for c in conclusions if c["severidade"] == "alta")
        medium_severity_count = sum(1 for c in conclusions if c["severidade"] == "media")
        
        if high_severity_count >= 3:
            summary = "Multiplos indicadores apontam forte possibilidade de manipulacao ou geracao artificial."
        elif high_severity_count >= 1 and medium_severity_count >= 2:
            summary = "Alguns indicadores sugerem possivel manipulacao. Recomenda-se analise complementar."
        elif high_severity_count >= 1:
            summary = "Ao menos um indicador apresenta anomalia significativa. Verificacao adicional recomendada."
        elif medium_severity_count >= 2:
            summary = "Pequenas inconsistencias detectadas. A imagem pode ter sofrido processamento leve."
        else:
            summary = "Os indicadores analisados sao consistentes com uma imagem autentica."
            
        return {
            "conclusoes": conclusions,
            "resumo": summary,
            "contagem": {
                "alta": high_severity_count,
                "media": medium_severity_count,
                "baixa": len(conclusions) - high_severity_count - medium_severity_count,
            }
        }
