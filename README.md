KINGAMBIT

Sistema web de analise forense experimental de imagens. O projeto combina
metadados, sinais estatisticos de imagem e quatro modelos neurais para estimar
se um arquivo apresenta indicios compativeis com manipulacao ou geracao por IA.

O Kingambit e uma ferramenta de triagem e apoio a investigacao. Ele nao prova
que uma imagem e autentica, editada ou gerada por IA.


ESTADO ATUAL

Runtime funcional com Flask.

Quatro modelos ativos: modelo_1, modelo_2, modelo_5 e modelo_6.

Quatro normalizadores correspondentes carregados pelo registro de modelos.

Ensemble com pesos aplicados somente na media final.

Frontend servido pela propria API.

Testes automatizados do backend disponiveis em tests/test_backend.py.


O QUE O SISTEMA FAZ

Para cada imagem enviada, o sistema pode:

1. Validar o arquivo por conteudo real, formato, extensao, dimensoes e pixels.
2. Extrair metadados usando ExifTool, com fallback para Pillow.
3. Categorizar sinais encontrados nos metadados.
4. Calcular indicadores forenses visuais.
5. Executar os quatro modelos ativos.
6. Agregar os scores com os pesos do ensemble.
7. Retornar uma classificacao conservadora e indicadores de discordancia.

O resultado deve ser interpretado junto com a imagem original e outras fontes
de evidencia. Ausencia de metadados ou score baixo nao significa autenticidade.


ARQUITETURA

server.py

E o ponto de entrada da aplicacao Flask. Tambem serve os arquivos estaticos de
public, registra os endpoints, limita uploads e coordena o pipeline completo.

core/metadata.py

Le metadados do arquivo. Quando o executavel ExifTool esta disponivel, ele e
usado com arquivo temporario e tratamento de falhas. Quando nao esta
disponivel, o sistema usa Pillow. Metadados sao sinais auxiliares e podem ser
removidos ou falsificados.

core/engine.py

Calcula os indicadores visuais:

ELA: erro de nivel de compressao apos recompressao JPEG.
SRM: variancia de ruido residual em blocos.
FFT: simetria aproximada no dominio da frequencia.
Correlacao RGB: relacao entre canais de cor.
Aberracao cromatica: desalinhamento entre bordas de canais.
Gradientes: media e desvio das magnitudes de borda.

Esses sinais dependem de formato, compressao, resolucao, camera, iluminacao,
conteudo e cadeia de edicao. Nenhum deles e uma prova isolada.

models/architecture.py

Define a arquitetura hibrida ModeloHibrido-EfficientNet-B0. Ela combina uma
EfficientNet-B0 para a imagem RGB, uma rede auxiliar para dez features
forenses, uma camada de fusao e uma saida escalar chamada logit.

Na avaliacao, a imagem e convertida para RGB, redimensionada para 224 por 224
e normalizada com os parametros ImageNet. As dez features sao normalizadas pelo
StandardScaler correspondente a cada modelo.

models/manager.py

Carrega pesos e normalizadores, verifica compatibilidade estrutural, valida
features, executa inferencia e calcula o ensemble. O carregamento usa
weights_only=True no PyTorch e rejeita normalizadores invalidos ou saidas nao
finitas.


MODELOS ATIVOS

Os modelos ativos sao definidos em model_manifest.json.

Modelo 1: IA Principal. Peso no ensemble: 3.0.
Modelo 2: IA Geral. Peso no ensemble: 2.5.
Modelo 5: IA Faces. Peso no ensemble: 1.0.
Modelo 6: IA Cenarios. Peso no ensemble: 1.0.

Os pesos nao alteram o treinamento, o score individual, a avaliacao de cada
modelo, o ranking dos modelos ou a calibracao. Eles afetam somente a media
final do ensemble.

A media final e calculada assim:

media final igual a score 1 vezes 3.0 mais score 2 vezes 2.5 mais score 5
vezes 1.0 mais score 6 vezes 1.0, dividido por 3.0 mais 2.5 mais 1.0 mais 1.0.

O score atual e obtido aplicando sigmoid ao logit e convertendo o resultado
para uma escala de 0 a 100. Ele nao e calibrado e nao deve ser lido como uma
probabilidade.

Cada modelo ativo precisa de dois arquivos na raiz:

modelo_1.pth e normalizador_1.joblib
modelo_2.pth e normalizador_2.joblib
modelo_5.pth e normalizador_5.joblib
modelo_6.pth e normalizador_6.joblib

O manifesto registra os hashes SHA-256 dos pesos e normalizadores para
verificacao de integridade.


CLASSIFICACOES RETORNADAS

baixo_indicio: poucos sinais no conjunto analisado.
indicios: sinais intermediarios que exigem avaliacao complementar.
suspeita_alta: score elevado com concordancia suficiente.
inconclusivo: poucos modelos ativos ou discordancia elevada.
indisponivel: nenhum modelo conseguiu produzir resultado.

Esses nomes descrevem risco estatistico do pipeline. Nao significam prova de
autenticidade, autoria, edicao ou origem.


API

GET /health

Retorna o estado do registro de modelos. Exemplo de resposta:

status: ok
modelos_ativos: 4
modelos_esperados: 4
dispositivo: cpu
capacidade_inferencia: true
modelos_com_falha: vazio

Retorna 503 quando nem todos os quatro modelos esperados estao ativos.

POST /analyze/quick

Recebe multipart com o campo file e executa somente metadados. Retorna exif e
categorias.

POST /analyze/deep

Executa metadados e analise forense visual. Retorna exif, categorias, imagem
ELA em Base64, mapas de ruido, FFT e gradiente, dez features e interpretacoes
heuristicas.

POST /analyze/full

Executa o pipeline completo e adiciona resultados individuais dos modelos,
scores, niveis, pesos usados no ensemble, media final, classificacao,
dispersao, discordancia e indicacao de que o score nao e calibrado.

Exemplo de chamada usando PowerShell:

Invoke-WebRequest -Uri http://127.0.0.1:5000/analyze/full -Method Post
-Form arquivo igual a Get-Item .\imagem.jpg

GET /formulario

Retorna o link de contato ou formulario configurado na aplicacao.

Rotas de interface:

GET / e GET /academico: interface principal.
GET /privacy: politica de privacidade.
GET /terms: termos de uso.
GET /css/arquivo: folhas de estilo.
GET /js/arquivo: scripts do frontend.
GET /assets/arquivo: recursos visuais.


UPLOADS E SEGURANCA

O backend aplica estas regras:

Limite de arquivo de 25 MiB.
Limite de requisicao HTTP acima do limite do arquivo.
Limite de 50 megapixels.
Dimensao minima de 16 por 16 pixels.
Verificacao do formato real com Pillow.
Extensao coerente com o formato real.
Rejeicao de imagens animadas ou com multiplos frames.
Protecao contra decompression bombs.
Rejeicao de arquivos corrompidos.
Erros controlados sem stack trace na resposta.
Cabecalho X-Content-Type-Options com valor nosniff.
Cabecalho X-Frame-Options com valor DENY.
Cabecalho Referrer-Policy com valor no-referrer.
Cabecalho Cache-Control com valor no-store.

Formatos aceitos atualmente: JPEG, PNG, WebP, TIFF e BMP. HEIC, HEIF, GIF,
RAW e outros formatos nao devem ser considerados suportados sem decodificacao
e testes especificos.


INSTALACAO LOCAL

Recomenda-se Python 3.11 ou superior compativel com as versoes fixadas em
requirements.txt.

No PowerShell:

Set-Location Z:\Kingambit-main
python -m pip install -r requirements.txt
python .\server.py

A aplicacao fica disponivel em http://127.0.0.1:5000.

Para alterar a porta:

$env:PORT igual a 8000
python .\server.py

O servidor de desenvolvimento Flask serve para testes locais. Para uma
implantacao real, use o container ou um servidor WSGI adequado atras de um
proxy com limites de recursos e controles operacionais.


DOCKER

Construir a imagem:

Set-Location Z:\Kingambit-main
docker build -t kingambit .

Executar:

docker run --rm -p 5000:5000 kingambit

O Dockerfile instala ExifTool, executa como usuario nao privilegiado, expoe a
porta 5000 e configura um healthcheck em /health.


TESTES E VERIFICACAO

Executar a suite:

Set-Location Z:\Kingambit-main
python -m unittest discover -s tests -v

Compilar os modulos principais:

python -m py_compile server.py core\metadata.py core\engine.py
models\architecture.py models\manager.py tests\test_backend.py

Verificar o healthcheck:

Invoke-WebRequest http://127.0.0.1:5000/health -UseBasicParsing

O teste de runtime deve confirmar quatro modelos ativos e nenhum erro de
carregamento. O repositorio final nao inclui os datasets originais nem os
scripts experimentais de treinamento.


ESTRUTURA DO RUNTIME

core contem engine.py e metadata.py.
models contem architecture.py e manager.py.
public contem academico.html, css, js e assets.
tests contem test_backend.py.
A raiz contem os quatro pares de pesos e normalizadores, model_manifest.json,
requirements.txt, Dockerfile e server.py.


LIMITACOES CONHECIDAS

Os datasets originais, labels completos, scripts de treinamento e metricas
independentes nao acompanham o runtime final. Tambem nao foi demonstrada a
independencia dos erros entre os quatro modelos.

Consequentemente, o score nao e uma probabilidade calibrada, nao existe
garantia de generalizacao para novos geradores, uma imagem real pode receber
score alto e uma imagem editada ou gerada pode receber score baixo.

Recompressao, redimensionamento e redes sociais podem alterar os sinais.
Metadados podem estar ausentes ou ser falsificados. Heatmaps nao constituem
prova. O benchmark historico foi pequeno e nao faz parte do runtime.

O sistema nao deve ser usado sozinho em decisoes juridicas, financeiras,
periciais ou de moderacao automatica.


RISCOS OPERACIONAIS RESTANTES

Antes de exposicao publica, ainda seria necessario avaliar ou implementar rate
limiting, autenticacao e autorizacao, limites de concorrencia, CPU e memoria,
sandbox adicional para ExifTool, proxy reverso com TLS, Content Security
Policy, observabilidade, alertas, teste de carga, lockfile de dependencias
com hashes e reavaliacao periodica contra novos geradores e editores.


INTEGRIDADE DOS ARTEFATOS

O arquivo model_manifest.json registra hashes SHA-256 dos modelos e
normalizadores ativos. Para verificar um arquivo individual:

Get-FileHash .\modelo_1.pth -Algorithm SHA256
Get-FileHash .\normalizador_1.joblib -Algorithm SHA256

Compare o resultado com o manifesto antes de iniciar o runtime quando os
artefatos forem transferidos entre maquinas.


USO RESPONSAVEL

O Kingambit deve ser usado como uma camada de triagem que ajuda uma pessoa a
decidir o que investigar. Uma conclusao deve considerar o arquivo original,
contexto de obtencao, cadeia de custodia, metadados, outras ferramentas e
avaliacao humana especializada.

O projeto nao deve afirmar que descobriu a origem definitiva de uma imagem.
