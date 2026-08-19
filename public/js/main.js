var arquivoAtual = null;

var uploadArea = document.getElementById('uploadArea');
var uploadInput = document.getElementById('uploadInput');
var uploadTexto = document.getElementById('uploadTexto');
var uploadNome = document.getElementById('uploadNome');
var btnAnalisar = document.getElementById('btnAnalisar');
var carregando = document.getElementById('carregando');
var erroGeral = document.getElementById('erroGeral');
var erroTexto = document.getElementById('erroTexto');
var sucessoGeral = document.getElementById('sucessoGeral');
var sucessoTexto = document.getElementById('sucessoTexto');
var resultadoGeral = document.getElementById('resultadoGeral');

if (uploadArea) {
    uploadArea.addEventListener('click', function() { uploadInput.click(); });

    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('arrastando');
    });

    uploadArea.addEventListener('dragleave', function() {
        uploadArea.classList.remove('arrastando');
    });

    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('arrastando');
        if (e.dataTransfer.files.length > 0) selecionarArquivo(e.dataTransfer.files[0]);
    });
}

if (uploadInput) {
    uploadInput.addEventListener('change', function() {
        if (uploadInput.files.length > 0) selecionarArquivo(uploadInput.files[0]);
    });
}

function comprimirImagem(arquivo, callback) {
    var MAX_WIDTH = 1920;
    var MAX_HEIGHT = 1080;
    var MAX_PIXELS = 1920 * 1080;
    var QUALITY = 0.8;
    var img = new Image();
    var reader = new FileReader();
    reader.onerror = function() { callback(null, 'Não foi possível ler a imagem selecionada.'); };
    reader.onload = function(e) {
        img.onload = function() {
            var w = img.width;
            var h = img.height;
            if (!w || !h) {
                callback(null, 'A imagem selecionada não possui dimensões válidas.');
                return;
            }
            var scale = Math.min(MAX_WIDTH / w, MAX_HEIGHT / h, Math.sqrt(MAX_PIXELS / (w * h)), 1);
            var nw = Math.round(w * scale);
            var nh = Math.round(h * scale);
            var canvas = document.createElement('canvas');
            canvas.width = nw;
            canvas.height = nh;
            var ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0, nw, nh);
            function concluirCompressao(blob) {
                if (blob) {
                    var nomeBase = arquivo.name.replace(/\.[^.]+$/, '');
                    var extensao = blob.type === 'image/webp' ? '.webp' : '.jpg';
                    var compressed = new File([blob], nomeBase + extensao, { type: blob.type });
                    callback(compressed, null);
                } else {
                    callback(null, 'Não foi possível comprimir a imagem no navegador.');
                }
                canvas.width = 0;
                canvas.height = 0;
            }
            canvas.toBlob(function(blob) {
                if (blob) {
                    concluirCompressao(blob);
                    return;
                }
                canvas.toBlob(concluirCompressao, 'image/jpeg', QUALITY);
            }, 'image/webp', QUALITY);
        };
        img.onerror = function() { callback(null, 'Formato de imagem não suportado pelo navegador.'); };
        img.src = e.target.result;
    };
    reader.readAsDataURL(arquivo);
}

function selecionarArquivo(arquivo) {
    if (!arquivo || !arquivo.type || arquivo.type.indexOf('image/') !== 0) {
        mostrarErro('Selecione um arquivo de imagem válido.');
        return;
    }
    mostrarCarregando('Preparando imagem');
    comprimirImagem(arquivo, function(comprimido, erro) {
        esconderCarregando();
        if (erro || !comprimido) {
            mostrarErro(erro || 'Não foi possível preparar a imagem.');
            return;
        }
        arquivoAtual = comprimido;
        uploadNome.textContent = arquivo.name;
        uploadNome.style.display = 'inline-flex';
        uploadArea.classList.add('com-arquivo');
        uploadTexto.textContent = 'Imagem preparada. Selecione outro arquivo para alterar.';
        btnAnalisar.disabled = false;
        esconderErro();
        mostrarSucesso('Imagem comprimida no navegador e pronta para análise.');
        resultadoGeral.style.display = 'none';
    });
}

function mostrarSkeleton() {
    resultadoGeral.style.display = 'block';
    var cardMeta = document.getElementById('cardMetadados');
    var cardAnalise = document.getElementById('cardAnaliseCompleta');
    var skeletonHtml = '';
    for (var s = 0; s < 5; s++) {
        skeletonHtml += '<div class="skeleton skeleton-line"></div>';
    }
    skeletonHtml += '<div class="skeleton skeleton-line short"></div>';
    document.getElementById('abaPainelIa').innerHTML = skeletonHtml;
    document.getElementById('abaPainelCamera').innerHTML = skeletonHtml;
    document.getElementById('abaPainelOutros').innerHTML = skeletonHtml;
    document.getElementById('metricasForensesGrid').innerHTML = '';
    document.getElementById('interpretacaoResumo').innerHTML = '';
    document.getElementById('interpretacaoResumo').className = 'interpretacao-resumo-caixa';
    document.getElementById('conclusoesLista').innerHTML = '';
    document.getElementById('juradoPrincipalContainer').innerHTML = '';
    document.getElementById('juradosAuxiliaresGrid').innerHTML = '';
}

function mostrarCarregando() {
    carregando.classList.add('ativo');
}
function esconderCarregando() {
    carregando.classList.remove('ativo');
}
function mostrarErro(msg) { esconderSucesso(); erroTexto.textContent = msg; erroGeral.classList.add('visivel'); }
function esconderErro() { erroGeral.classList.remove('visivel'); }
function mostrarSucesso(msg) {
    if (sucessoTexto) sucessoTexto.textContent = msg;
    if (sucessoGeral) sucessoGeral.classList.add('visivel');
}
function esconderSucesso() {
    if (sucessoGeral) sucessoGeral.classList.remove('visivel');
}

var menuToggle = document.getElementById('menuToggle');
var navLinks = document.getElementById('navLinks');
if (menuToggle && navLinks) {
    menuToggle.addEventListener('click', function() {
        var aberto = navLinks.classList.toggle('aberto');
        menuToggle.setAttribute('aria-expanded', String(aberto));
        menuToggle.setAttribute('aria-label', aberto ? 'Fechar menu' : 'Abrir menu');
    });
    navLinks.addEventListener('click', function(event) {
        if (event.target.tagName === 'A') {
            navLinks.classList.remove('aberto');
            menuToggle.setAttribute('aria-expanded', 'false');
            menuToggle.setAttribute('aria-label', 'Abrir menu');
        }
    });
}

function escapeHtml(texto) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(texto));
    return div.innerHTML;
}

function criarTabela(dados) {
    if (!dados || Object.keys(dados).length === 0) {
        return '<div class="meta-vazio">Nenhum registro técnico mapeado nesta categoria</div>';
    }
    var html = '<table class="meta-tabela">';
    var chaves = Object.keys(dados);
    for (var i = 0; i < chaves.length; i++) {
        html += '<tr><td>' + escapeHtml(chaves[i]) + '</td><td>' + escapeHtml(String(dados[chaves[i]])) + '</td></tr>';
    }
    html += '</table>';
    return html;
}

function trocarAbaMetadados(indice) {
    var abas = document.querySelectorAll('.aba-btn');
    var paineis = document.querySelectorAll('.aba-painel');

    for (var i = 0; i < abas.length; i++) {
        abas[i].classList.remove('ativa');
        paineis[i].classList.remove('ativa');
    }

    abas[indice].classList.add('ativa');
    paineis[indice].classList.add('ativa');
}

function renderizarReviews(dados, colunas) {
    var colNome = colunas.find(function(c) { return c.toLowerCase().indexOf('nome') !== -1; }) || colunas[1] || '';
    var colData = colunas.find(function(c) { return c.toLowerCase().indexOf('carimbo') !== -1 || c.toLowerCase().indexOf('data') !== -1 || c.toLowerCase().indexOf('hora') !== -1; }) || colunas[0] || '';
    var colInternet = colunas.find(function(c) { return c.toLowerCase().indexOf('conectado') !== -1 || c.toLowerCase().indexOf('internet') !== -1; }) || '';
    var colFamiliaridade = colunas.find(function(c) { return c.toLowerCase().indexOf('familiaridade') !== -1; }) || '';

    var colClassificacoes = colunas.filter(function(c) {
        var cl = c.toLowerCase();
        return (cl.indexOf('classifica') !== -1 || cl.indexOf('origem') !== -1) && cl.indexOf('método') === -1 && cl.indexOf('metodo') === -1;
    });
    var colMetodos = colunas.filter(function(c) {
        var cl = c.toLowerCase();
        return cl.indexOf('método') !== -1 || cl.indexOf('metodo') !== -1;
    });

    dados.sort(function(a, b) {
        var nomeA = (a[colNome] || '').toString().toLowerCase();
        var nomeB = (b[colNome] || '').toString().toLowerCase();
        return nomeA.localeCompare(nomeB);
    });

    function encurtarFamiliaridade(fam) {
        if (!fam) return 'Médio';
        var f = fam.toString();
        if (f.indexOf('5 -') !== -1) return 'Perito (Especialista)';
        if (f.indexOf('4 -') !== -1) return 'Alto';
        if (f.indexOf('3 -') !== -1) return 'Médio';
        if (f.indexOf('2 -') !== -1) return 'Baixo';
        if (f.indexOf('1 -') !== -1) return 'Iniciante';
        return f;
    }

    function encurtarMetodo(metodo) {
        if (!metodo) return 'Não Especificado';
        var m = metodo.toString();
        if (m.indexOf('Percepção visual') !== -1) return 'Inspeção Óptica';
        if (m.indexOf('Metadados') !== -1) return 'Validação EXIF';
        if (m.indexOf('ELA') !== -1 || m.indexOf('Error') !== -1) return 'Diferencial ELA';
        if (m.indexOf('SRM') !== -1 || m.indexOf('Ruído') !== -1) return 'Análise de Ruído';
        if (m.indexOf('FFT') !== -1 || m.indexOf('Frequência') !== -1) return 'Espectro Fourier';
        return m.substring(0, 24);
    }

    function formatarData(dataStr) {
        if (!dataStr) return '';
        try {
            var d = new Date(dataStr.replace(/-/g, '/'));
            if (isNaN(d.getTime())) {
                return dataStr.split('.')[0] || dataStr;
            }
            var dia = String(d.getDate()).padStart(2, '0');
            var mes = String(d.getMonth() + 1).padStart(2, '0');
            var ano = d.getFullYear();
            var horas = String(d.getHours()).padStart(2, '0');
            var minutos = String(d.getMinutes()).padStart(2, '0');
            return dia + '/' + mes + '/' + ano + ' ' + horas + ':' + minutos;
        } catch(e) {
            return dataStr;
        }
    }

    var html = '';
    for (var i = 0; i < dados.length; i++) {
        var item = dados[i];
        var nome = item[colNome] || 'Auditor Técnico';
        var dataOriginal = item[colData] || '';
        var dataFmt = formatarData(dataOriginal);
        var internet = item[colInternet] || 'Não informada';
        var familiaridadeOriginal = item[colFamiliaridade] || '';
        var familiaridadeFmt = encurtarFamiliaridade(familiaridadeOriginal);

        var famClass = 'f-media';
        var famLower = familiaridadeFmt.toLowerCase();
        if (famLower.indexOf('perito') !== -1 || famLower.indexOf('especialista') !== -1) famClass = 'f-muito-alta';
        else if (famLower.indexOf('alta') !== -1 || famLower.indexOf('alto') !== -1) famClass = 'f-alta';
        else if (famLower.indexOf('baixa') !== -1 || famLower.indexOf('baixo') !== -1) famClass = 'f-baixa';

        var totalReal = 0;
        var totalIA = 0;
        for (var k = 0; k < colClassificacoes.length; k++) {
            var valClass = (item[colClassificacoes[k]] || '').toString();
            if (valClass.indexOf('procedência real') !== -1 || valClass.toLowerCase().indexOf('real') !== -1) {
                totalReal++;
            } else if (valClass.indexOf('manipulação') !== -1 || valClass.toLowerCase().indexOf('artificial') !== -1 || valClass.toLowerCase().indexOf('ia') !== -1) {
                totalIA++;
            }
        }

        html += '<div class="review-card" onclick="toggleReview(' + i + ', event)">';
        html += '  <div class="review-header">';
        html += '    <div class="review-header-left">';
        html += '      <div class="review-icon-box">';
        html += '        <svg style="width:14px; height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
        html += '      </div>';
        html += '      <div>';
        html += '        <div class="review-nome">' + escapeHtml(nome.toString()) + '</div>';
        html += '        <div class="review-data">' + escapeHtml(dataFmt) + '</div>';
        html += '      </div>';
        html += '    </div>';
        html += '    <div class="review-header-right">';
        html += '      <span class="tag-familiaridade ' + famClass + '">' + escapeHtml(familiaridadeFmt) + '</span>';
        html += '      <span class="tag-detalhes-toggle">▼</span>';
        html += '    </div>';
        html += '  </div>';

        html += '  <div class="review-detalhes" id="review-' + i + '" onclick="event.stopPropagation()">';
        html += '    <div class="laudo-banner">';
        html += '      <div>';
        html += '        <div class="laudo-banner-titulo">Laudo Pericial Consolidado</div>';
        html += '        <div class="laudo-banner-sub">Auditoria forense de validação estrutural</div>';
        html += '      </div>';
        html += '      <div style="text-align: right;">';
        html += '        <div style="font-size: 10px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.5px; text-transform: uppercase;">CLASSIFICAÇÃO</div>';
        html += '        <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px; font-weight: 600;">Autêntico: ' + totalReal + ' | Sintético (IA): ' + totalIA + '</div>';
        html += '      </div>';
        html += '    </div>';

        html += '    <div class="laudo-perito-meta">';
        html += '      <div><strong>Familiaridade:</strong> ' + escapeHtml(familiaridadeOriginal.toString()) + '</div>';
        html += '      <div style="margin-left: auto;"><strong>Auditado com Internet:</strong> ' + escapeHtml(internet.toString()) + '</div>';
        html += '    </div>';

        html += '    <div class="amostras-grid">';
        for (var j = 0; j < 8; j++) {
            var colClass = colClassificacoes[j];
            var colMet = colMetodos[j];

            var valorClass = colClass ? (item[colClass] || '') : '';
            var valorMet = colMet ? (item[colMet] || '') : '';

            var isReal = valorClass.indexOf('procedência real') !== -1 || valorClass.toLowerCase().indexOf('real') !== -1;
            var labelClass = isReal ? 'AUTÊNTICO' : 'IA / SINTÉTICO';
            var classStyle = isReal ? 'v-real' : 'v-ia';

            html += '      <div class="amostra-card">';
            html += '        <div class="amostra-titulo">AMOSTRA #' + (j + 1) + '</div>';
            html += '        <div class="amostra-veredicto ' + classStyle + '">' + labelClass + '</div>';
            html += '        <div class="amostra-metodo" title="' + escapeHtml(valorMet.toString()) + '">' + escapeHtml(encurtarMetodo(valorMet)) + '</div>';
            html += '      </div>';
        }
        html += '    </div>';
        html += '  </div>';
        html += '</div>';
    }
    lista.innerHTML = html;
}

function toggleReview(idx, event) {
    if (event) {
        var card = event.currentTarget;
        card.classList.toggle('aberto');
    } else {
        var el = document.getElementById('review-' + idx);
        if (el) {
            var card = el.closest('.review-card');
            if (card) card.classList.toggle('aberto');
        }
    }
}

var buscaReviews = document.getElementById('buscaReviews');
if (buscaReviews) {
    buscaReviews.addEventListener('input', function() {
        var termo = this.value.toLowerCase();
        var cards = document.querySelectorAll('.review-card');
        for (var i = 0; i < cards.length; i++) {
            var nome = cards[i].querySelector('.review-nome').textContent.toLowerCase();
            cards[i].style.display = nome.indexOf(termo) !== -1 ? 'block' : 'none';
        }
    });
}

function ampliarImagem(container) {
    var img = container.querySelector('img');
    var modal = document.getElementById('modalVisualizador');
    var imagemAmpliada = document.getElementById('imagemAmpliada');
    imagemAmpliada.src = img.src;
    modal.classList.add('ativo');
}

function fecharAmpliador() {
    document.getElementById('modalVisualizador').classList.remove('ativo');
}

function atualizarGauge(score) {
    var progresso = document.getElementById('gaugeProgresso');
    var txtScore = document.getElementById('gaugeScore');
    var statusBadge = document.getElementById('bancadaStatusBadge');

    var perimetro = 283;
    var offset = perimetro - (score / 100) * perimetro;

    progresso.style.strokeDashoffset = offset;
    txtScore.textContent = score + '%';

    progresso.style.stroke = 'var(--status-success)';
    statusBadge.className = 'bancada-status-badge status-baixo';
    statusBadge.textContent = 'Autenticidade Confirmada';

    if (score >= 70) {
        progresso.style.stroke = 'var(--status-danger)';
        statusBadge.className = 'bancada-status-badge status-alto';
        statusBadge.textContent = 'Forte Suspeita de IA';
    } else if (score >= 40) {
        progresso.style.stroke = 'var(--status-warning)';
        statusBadge.className = 'bancada-status-badge status-medio';
        statusBadge.textContent = 'Indicações de Edição';
    }
}

if (btnAnalisar) {
    btnAnalisar.addEventListener('click', function() {
        if (!arquivoAtual) return;
        esconderErro();
        esconderSucesso();
        mostrarCarregando();
        mostrarSkeleton();

        var fd = new FormData();
        fd.append('file', arquivoAtual);

        var controller = new AbortController();
        var timeoutId = setTimeout(function() { controller.abort(); }, 120000);

        fetch('/analyze/full', { method: 'POST', body: fd, signal: controller.signal })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                clearTimeout(timeoutId);
                esconderCarregando();
                if (d.erro) { mostrarErro(d.erro); return; }
                mostrarSucesso('Análise concluída. Os resultados técnicos estão disponíveis abaixo.');

                var cat = d.categorias;

                var painelIa = document.getElementById('abaPainelIa');
                var htmlIa = '';
                if (cat.indicios_ia && cat.indicios_ia.length > 0) {
                    for (var i = 0; i < cat.indicios_ia.length; i++) {
                        var ind = cat.indicios_ia[i];
                        htmlIa += '<div class="indicio-card">';
                        htmlIa += '<div class="indicio-campo">' + escapeHtml(ind.campo) + '</div>';
                        htmlIa += '<div class="indicio-valor">' + escapeHtml(String(ind.valor)) + '</div>';
                        htmlIa += '<div class="indicio-motivo">' + escapeHtml(ind.motivo) + '</div>';
                        htmlIa += '</div>';
                    }
                }
                if (cat.ia && Object.keys(cat.ia).length > 0) {
                    htmlIa += criarTabela(cat.ia);
                }
                if ((!cat.indicios_ia || cat.indicios_ia.length === 0) && (!cat.ia || Object.keys(cat.ia).length === 0)) {
                    htmlIa += '<div class="meta-vazio">Nenhum metadado de IA suspeito encontrado. Os metadados parecem autênticos ou foram removidos.</div>';
                }
                painelIa.innerHTML = htmlIa;

                var painelCamera = document.getElementById('abaPainelCamera');
                var htmlCamera = '';
                if (cat.camera && Object.keys(cat.camera).length > 0) {
                    htmlCamera += criarTabela(cat.camera);
                } else {
                    htmlCamera += '<div class="meta-vazio">Nenhum metadado físico de câmera/sensor encontrado.</div>';
                }
                painelCamera.innerHTML = htmlCamera;

                var painelOutros = document.getElementById('abaPainelOutros');
                painelOutros.innerHTML = criarTabela(d.exif);

                trocarAbaMetadados(0);

                var bancada = d.bancada;
                atualizarGauge(bancada.media_geral);

                var containerPrincipal = document.getElementById('juradoPrincipalContainer');
                var containerAuxiliares = document.getElementById('juradosAuxiliaresGrid');

                var dadosPrincipal = bancada.modelos['modelo_1'];
                var htmlPrincipal = '';

                if (dadosPrincipal) {
                    var corTextoPri = 'var(--status-success)';
                    var textNivelPri = 'Risco Baixo';
                    if (dadosPrincipal.nivel === 'Alto') {
                        corTextoPri = 'var(--status-danger)';
                        textNivelPri = 'Risco Alto';
                    } else if (dadosPrincipal.nivel === 'Medio') {
                        corTextoPri = 'var(--status-warning)';
                        textNivelPri = 'Risco Médio';
                    }

                    htmlPrincipal += '<div class="jurado-principal-card">';
                    htmlPrincipal += '  <div class="jurado-principal-info">';
                    htmlPrincipal += '    <div class="jurado-principal-badge">RECOMENDADO</div>';
                    htmlPrincipal += '    <span class="jurado-principal-nome">' + escapeHtml(dadosPrincipal.nome) + '</span>';
                    htmlPrincipal += '    <span class="jurado-principal-desc">Modelo estatístico primário calibrado para desvios espaciais de alta frequência.</span>';
                    htmlPrincipal += '  </div>';
                    htmlPrincipal += '  <div class="jurado-principal-nota-box">';
                    htmlPrincipal += '    <span class="jurado-principal-score" style="color: ' + corTextoPri + '">' + dadosPrincipal.score + '%</span>';
                    htmlPrincipal += '    <span class="jurado-principal-status" style="color: ' + corTextoPri + '; font-weight: 700; font-size: 11px; margin-top:4px;">' + textNivelPri + '</span>';
                    htmlPrincipal += '    <span class="jurado-principal-peso" style="margin-top:2px;">Peso: ' + dadosPrincipal.peso + 'x</span>';
                    htmlPrincipal += '  </div>';
                    htmlPrincipal += '</div>';
                } else {
                    htmlPrincipal += '<div class="jurado-principal-card jurado-inativo">';
                    htmlPrincipal += '  <div class="jurado-principal-info">';
                    htmlPrincipal += '    <div class="jurado-principal-badge" style="background: var(--text-muted);">INDISPONÍVEL</div>';
                    htmlPrincipal += '    <span class="jurado-principal-nome">Modelo Principal</span>';
                    htmlPrincipal += '    <span class="jurado-principal-desc">IA Principal indisponível na raiz do projeto.</span>';
                    htmlPrincipal += '  </div>';
                    htmlPrincipal += '  <div class="jurado-principal-nota-box">';
                    htmlPrincipal += '    <span class="jurado-principal-score" style="color: var(--text-muted)">--%</span>';
                    htmlPrincipal += '    <span class="jurado-principal-peso">Peso: 10x</span>';
                    htmlPrincipal += '  </div>';
                    htmlPrincipal += '</div>';
                }
                containerPrincipal.innerHTML = htmlPrincipal;

                var modelosAuxiliares = [
                    { id: 'modelo_2', padrao: 'IA Geral' },
                    { id: 'modelo_3', padrao: 'IA Multicategoria' },
                    { id: 'modelo_4', padrao: 'IA Face Detection' }
                ];

                var htmlAuxiliares = '';
                for (var m = 0; m < modelosAuxiliares.length; m++) {
                    var mod = modelosAuxiliares[m];
                    var dadosMod = bancada.modelos[mod.id];

                    if (dadosMod) {
                        var corTexto = 'var(--status-success)';
                        var textNivel = 'Risco Baixo';
                        if (dadosMod.nivel === 'Alto') {
                            corTexto = 'var(--status-danger)';
                            textNivel = 'Risco Alto';
                        } else if (dadosMod.nivel === 'Medio') {
                            corTexto = 'var(--status-warning)';
                            textNivel = 'Risco Médio';
                        }

                        htmlAuxiliares += '<div class="jurado-aux-card">';
                        htmlAuxiliares += '  <div class="jurado-aux-info">';
                        htmlAuxiliares += '    <span class="jurado-aux-nome">' + escapeHtml(dadosMod.nome);
                        htmlAuxiliares += '    </span>';
                        htmlAuxiliares += '    <span class="jurado-aux-status" style="color: ' + corTexto + '">' + textNivel + '</span>';
                        htmlAuxiliares += '    <span class="jurado-aux-peso">Peso: ' + dadosMod.peso + 'x</span>';
                        htmlAuxiliares += '  </div>';
                        htmlAuxiliares += '  <div class="jurado-aux-score" style="color: ' + corTexto + '">' + dadosMod.score + '%</div>';
                        htmlAuxiliares += '</div>';
                    } else {
                        htmlAuxiliares += '<div class="jurado-aux-card jurado-inativo">';
                        htmlAuxiliares += '  <div class="jurado-aux-info">';
                        htmlAuxiliares += '    <span class="jurado-aux-nome">' + escapeHtml(mod.padrao);
                        htmlAuxiliares += '    </span>';
                        htmlAuxiliares += '    <span class="jurado-aux-status" style="color: var(--text-muted)">Indisponível</span>';
                        htmlAuxiliares += '  </div>';
                        htmlAuxiliares += '  <div class="jurado-aux-score" style="color: var(--text-muted)">--%</div>';
                        htmlAuxiliares += '</div>';
                    }
                }
                containerAuxiliares.innerHTML = htmlAuxiliares;

                var urlOriginal = URL.createObjectURL(arquivoAtual);
                document.getElementById('mapaOriginal').src = urlOriginal;
                document.getElementById('mapaEla').src = 'data:image/png;base64,' + d.ela;
                document.getElementById('mapaRuido').src = 'data:image/png;base64,' + d.forense.mapa_ruido_b64;
                document.getElementById('mapaGradiente').src = 'data:image/png;base64,' + d.forense.mapa_gradiente_b64;
                document.getElementById('mapaFft').src = 'data:image/png;base64,' + d.forense.fft_mapa_b64;

                var forense = d.forense;
                var metricasGrid = document.getElementById('metricasForensesGrid');
                var htmlMetricas = '';

                var metricasDicionario = [
                    { v: forense.variancia_ruido, l: 'Variância Ruído SRM', threshold: 3, rule: 'abaixo', desc: 'Indica ausência de flutuação térmica natural se menor que 3.0.' },
                    { v: forense.fft_simetria, l: 'Simetria Fourier (FFT)', threshold: 0.95, rule: 'acima', desc: 'Se superior a 0.95, sugere repetição geométrica típica de grades artificiais de IA.' },
                    { v: forense.aberracao_cromatica, l: 'Aberração Cromática', threshold: 0.03, rule: 'abaixo', desc: 'A ausência total de desalinhamento óptico (menor que 0.03) é um forte indicador de imagens sintéticas.' },
                    { v: forense.correlacao_rgb.rg, l: 'Correlação R-G', threshold: 0.98, rule: 'acima', desc: 'Canais redundantes se acima de 0.98.' },
                    { v: forense.correlacao_rgb.rb, l: 'Correlação R-B', threshold: 0.98, rule: 'acima', desc: 'Canais redundantes se acima de 0.98.' },
                    { v: forense.correlacao_rgb.gb, l: 'Correlação G-B', threshold: 0.98, rule: 'acima', desc: 'Canais redundantes se acima de 0.98.' },
                    { v: forense.gradiente_media, l: 'Média de Gradientes', threshold: 5, rule: 'abaixo', desc: 'Suavização ou filtragem artificial se inferior a 5.0.' },
                    { v: forense.gradiente_desvio, l: 'Desvio de Gradientes', threshold: 8, rule: 'abaixo', desc: 'Bordas e contrastes anormalmente idênticos se menor que 8.0.' },
                    { v: forense.ela_media, l: 'Média ELA %', threshold: 15, rule: 'abaixo', desc: 'Níveis de compressão excessivamente uniformes se menor que 15.0%.' }
                ];

                for (var mt = 0; mt < metricasDicionario.length; mt++) {
                    var itemMt = metricasDicionario[mt];
                    var anomalo = false;

                    if (itemMt.rule === 'abaixo') {
                        if (itemMt.v < itemMt.threshold) anomalo = true;
                    } else if (itemMt.rule === 'acima') {
                        if (itemMt.v > itemMt.threshold) anomalo = true;
                    }

                    var classeCard = anomalo ? 'metrica-card metrica-anomala' : 'metrica-card';
                    var corNum = anomalo ? 'var(--status-danger)' : 'var(--text-primary)';

                    htmlMetricas += '<div class="' + classeCard + '" title="' + escapeHtml(itemMt.desc) + '">';
                    htmlMetricas += '  <div class="metrica-valor" style="color: ' + corNum + '">' + itemMt.v + '</div>';
                    htmlMetricas += '  <div class="metrica-label">' + escapeHtml(itemMt.l) + '</div>';
                    htmlMetricas += '</div>';
                }
                metricasGrid.innerHTML = htmlMetricas;

                var interp = forense.interpretacao;
                var classeResumo = 'resumo-baixo';

                if (interp.contagem.alta >= 3) {
                    classeResumo = 'resumo-alto';
                } else if (interp.contagem.alta >= 1 || interp.contagem.media >= 2) {
                    classeResumo = 'resumo-medio';
                }

                var divResumo = document.getElementById('interpretacaoResumo');
                divResumo.className = 'interpretacao-resumo-caixa ' + classeResumo;
                divResumo.innerHTML = '<span>' + escapeHtml(interp.resumo) + '</span>';

                var divConclusoes = document.getElementById('conclusoesLista');
                var htmlConclusoes = '';
                for (var c = 0; c < interp.conclusoes.length; c++) {
                    var conc = interp.conclusoes[c];
                    htmlConclusoes += '<div class="conclusao-card">';
                    htmlConclusoes += '  <div class="conclusao-topo">';
                    htmlConclusoes += '    <span class="conclusao-area">' + escapeHtml(conc.area) + '</span>';
                    htmlConclusoes += '    <span class="conclusao-severidade sev-' + conc.severidade + '">' + conc.severidade + '</span>';
                    htmlConclusoes += '  </div>';
                    htmlConclusoes += '  <div class="conclusao-indicador">' + escapeHtml(conc.indicador) + '</div>';
                    htmlConclusoes += '  <div class="conclusao-interpretacao">' + escapeHtml(conc.interpretacao) + '</div>';
                    htmlConclusoes += '  <div class="conclusao-valor">Nível de desvio estrutural: ' + conc.valor + '</div>';
                    htmlConclusoes += '</div>';
                }
                divConclusoes.innerHTML = htmlConclusoes;

                resultadoGeral.style.display = 'block';
                resultadoGeral.scrollIntoView({ behavior: 'smooth' });
            })
            .catch(function(err) {
                clearTimeout(timeoutId);
                esconderCarregando();
                console.error(err);
                if (err.name === 'AbortError') {
                    mostrarErro('A análise demorou demais e foi cancelada. Tente com uma imagem menor.');
                } else {
                    mostrarErro('Falha técnica de comunicação ou erro no processamento das transformações físicas.');
                }
            });
    });
}

(function() {
    const btnNoturno = document.getElementById('btnModoNoturno');
    const svgNoturno = document.getElementById('svgModoNoturno');
    const txtNoturno = document.getElementById('textoModoNoturno');

    let modoNoturno = JSON.parse(localStorage.getItem('modoNoturno') || 'false');

    const sunSvgHtml = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    const moonSvgHtml = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';

    function atualizarInterfaceNoturno() {
        if (modoNoturno) {
            document.body.classList.add('noturno');
            if (svgNoturno) svgNoturno.innerHTML = sunSvgHtml;
            if (txtNoturno) txtNoturno.textContent = 'Modo Claro';
        } else {
            document.body.classList.remove('noturno');
            if (svgNoturno) svgNoturno.innerHTML = moonSvgHtml;
            if (txtNoturno) txtNoturno.textContent = 'Modo Noturno';
        }
    }

    if (btnNoturno) {
        btnNoturno.addEventListener('click', function() {
            modoNoturno = !modoNoturno;
            localStorage.setItem('modoNoturno', modoNoturno);
            atualizarInterfaceNoturno();
        });
    }

    atualizarInterfaceNoturno();
})();
