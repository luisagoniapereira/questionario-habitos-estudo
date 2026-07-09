# -*- coding: utf-8 -*-
"""
=============================================================================
REPRODUCAO COMPLETA DAS ANALISES DO ARTIGO (QUANTITATIVAS E TEXTUAIS)
"Study Engagement, Self-Regulation and Well-Being in Hybrid Higher Education"
(Universidade Atlantica, n = 69)
=============================================================================

O QUE ESTE PROGRAMA FAZ
-----------------------
Reproduz, do principio ao fim, todas as analises quantitativas do artigo:

  1. Carrega o conjunto de dados: le o ficheiro local "Questionario_Limpo.xlsx"
     se estiver ao lado do programa, ou descarrega-o do Zenodo
     (DOI 10.5281/zenodo.17127602) caso contrario.
  2. Reconstroi os quatro indices usados no artigo (bem-estar, gestao do tempo,
     estrategias online e horas de estudo semanais).
  3. Calcula a fiabilidade (KR-20) de cada indice.
  4. Produz as estatisticas descritivas (Tabela 4).
  5. Calcula as correlacoes de Spearman (Tabela 5 e Figura 3).
  6. Compara os sexos com o teste de Mann-Whitney e o delta de Cliff (Tabela 6).
  7. Estima a regressao robusta de Huber, com e sem os casos atipicos (Tabela 6).
  8. Executa a analise de agrupamento (k-means) com validacao explicita:
     silhueta, estabilidade bootstrap e concordancia com Ward (Figuras 5a/5b,
     Tabela 8).
  9. Analisa as respostas abertas por categoria tematica a priori (Seccao 3.9):
     frequencias de termos no corpus (Figura 6) e termos caracteristicos de
     cada categoria, por razao de verosimilhanca G2 (Tabela 10).

NOTA SOBRE O AMBITO
-------------------
Nesta versao, o programa cobre TANTO a componente quantitativa COMO a analise
lexical das respostas abertas (Seccao 3.9). A Seccao 3.9 deixou de depender do
Orange Data Mining: a analise por categorias tematicas definidas a priori e
reproduzida integralmente por este programa, a partir do mesmo ficheiro de
dados.

COMO EXECUTAR
-------------
    pip install pandas numpy scipy statsmodels scikit-learn matplotlib openpyxl
    python reproducao_analise.py

As figuras sao gravadas na pasta ./figuras/ e os resultados numericos sao
impressos no ecra.

REPRODUTIBILIDADE
-----------------
A semente aleatoria (RANDOM_STATE) e fixada em todos os passos estocasticos
(k-means e bootstrap), para que os resultados sejam identicos em cada execucao.

Escrito com comentarios extensos porque se destina a contexto de ensino: cada
bloco explica nao so O QUE faz, mas tambem PORQUE se faz assim.
=============================================================================
"""

# ---------------------------------------------------------------------------
# 0. IMPORTACOES E CONFIGURACAO GLOBAL
# ---------------------------------------------------------------------------
import io                      # Tratar o ficheiro descarregado em memoria.
import re                      # Expressoes regulares (limpeza do texto livre).
import zipfile                 # O dataset do Zenodo vem comprimido num .zip.
import urllib.request          # Descarregar o ficheiro do Zenodo.
import unicodedata             # Remover acentos ao comparar textos.
from pathlib import Path       # Manipular caminhos de ficheiros de forma robusta.

import numpy as np             # Calculo numerico (vetores e matrizes).
import pandas as pd            # Estruturas de dados tabulares (DataFrame).
from scipy import stats        # Testes estatisticos (Spearman, Mann-Whitney).
import statsmodels.api as sm   # Regressao robusta (estimador de Huber) e OLS.

from sklearn.preprocessing import StandardScaler            # Padronizacao (z-scores).
from sklearn.cluster import KMeans, AgglomerativeClustering # Agrupamento.
from sklearn.decomposition import PCA                       # Reducao de dimensao.
from sklearn.metrics import (                               # Metricas de validacao.
    silhouette_score,
    calinski_harabasz_score,
    adjusted_rand_score,
)

import matplotlib
matplotlib.use("Agg")          # Backend nao-interativo (grava ficheiros sem ecra).
import matplotlib.pyplot as plt

# --- Constantes de configuracao (centralizadas para facil adaptacao) --------
# Identificador do registo no Zenodo (o mesmo para todas as versoes; a API
# "records/<id>" resolve para a versao mais recente). Usamos a API para
# descobrir dinamicamente o ficheiro de dados, o que evita ter de codificar
# aqui o numero de versao e continua a funcionar quando forem publicadas
# novas versoes do registo.
# Nota: se o ficheiro "Questionario_Limpo.xlsx" estiver na mesma pasta que este
# programa (como no pacote completo do Zenodo), os dados sao lidos localmente e
# a API nem chega a ser usada.
ZENODO_RECORD_ID = "17127602"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
RANDOM_STATE = 42                    # Semente para resultados reproduziveis.
NOME_FICHEIRO_LOCAL = "Questionario_Limpo.xlsx"  # Ficheiro de dados ao lado do script.
PASTA_FIGURAS = Path("figuras")
PASTA_FIGURAS.mkdir(exist_ok=True)   # Cria a pasta ./figuras/ se nao existir.


# ---------------------------------------------------------------------------
# FUNCOES AUXILIARES DE BAIXO NIVEL
# ---------------------------------------------------------------------------
def sem_acentos(texto):
    """Remove acentos de uma string (para comparar, p. ex., 'sozinho')."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def item_binario(dados, coluna, inverter=False):
    """
    Converte uma coluna 'Sim'/'Nao' em 1/0.

    Alguns itens sao "invertidos": por exemplo, "sente cansaco fisico" e uma
    indicacao NEGATIVA de bem-estar, por isso um 'Sim' deve contar como 0
    (menos bem-estar). O parametro `inverter=True` trata esses casos.

    NOTA: o reconhecimento e tolerante a acentos e a maiusculas/minusculas.
    No ficheiro original a resposta negativa e "Nao" (com til: N-a-tilde-o); em
    vez de depender da grafia exata, normalizamos cada valor (removendo acentos
    e passando a minusculas) antes de o classificar. Assim o programa funciona
    mesmo que o ficheiro use "Sim/Nao", "sim/nao" ou variantes acentuadas.
    """
    def classificar(valor):
        if pd.isna(valor):
            return np.nan
        v = sem_acentos(str(valor).strip().lower())  # normaliza: "Nao" -> "nao"
        if v == "sim":
            return 1
        if v == "nao":
            return 0
        return np.nan  # qualquer outro valor fica como ausente
    s = dados[coluna].apply(classificar)
    return 1 - s if inverter else s


def kr20(matriz_itens):
    """
    Calcula o coeficiente Kuder-Richardson 20 (KR-20).

    O KR-20 e a versao do alfa de Cronbach para itens DICOTOMICOS (0/1). Mede a
    consistencia interna: ate que ponto os itens de um indice "andam juntos".
    Varia entre 0 e 1; valores acima de .70 sao convencionalmente aceitaveis.

    Formula:  KR-20 = (k / (k-1)) * (1 - soma(p_i * q_i) / variancia_total)
      onde  k = numero de itens
            p_i = proporcao de respostas 1 no item i
            q_i = 1 - p_i
            variancia_total = variancia da soma dos itens
    """
    itens = matriz_itens.dropna()
    k = itens.shape[1]
    p = itens.mean()
    q = 1 - p
    variancia_total = itens.sum(axis=1).var(ddof=1)  # ddof=1: variancia amostral.
    return (k / (k - 1)) * (1 - (p * q).sum() / variancia_total)


def cliff_delta(a, b):
    """
    Calcula o delta de Cliff, uma medida de tamanho de efeito NAO-parametrica.

    Responde a pergunta: "se escolhermos ao acaso um valor de cada grupo, qual e
    a probabilidade de um exceder o outro?". Varia de -1 a +1 (0 = sem diferenca).
    Interpretacao convencional: |d| < .147 negligivel, < .33 pequeno, < .474 medio.

    Calcula-se a partir da estatistica U de Mann-Whitney, o que e mais eficiente
    do que contar todos os pares diretamente.
    """
    a, b = np.asarray(a), np.asarray(b)
    n1, n2 = len(a), len(b)
    U, _ = stats.mannwhitneyu(a, b, alternative="two-sided")
    return (2 * U) / (n1 * n2) - 1


# ---------------------------------------------------------------------------
# 1. CARREGAR OS DADOS (ficheiro local ao lado do script, ou Zenodo)
# ---------------------------------------------------------------------------
def _extrair_dados_de_excel(caminho_ou_buffer):
    """
    Le o ficheiro Excel e devolve (header, dados), onde `header` e uma Series
    com o TEXTO de cada pergunta e `dados` e o DataFrame das respostas, com as
    colunas numeradas de 1 a 67.

    O ficheiro de dados circulou em DUAS variantes, e o programa aceita ambas:

      Variante A (registo do Zenodo): as colunas ja estao numeradas de 1 a 67
        e a PRIMEIRA linha contem o texto das perguntas; as respostas comecam
        na segunda linha.
      Variante B (ficheiro de trabalho): o texto das perguntas esta no proprio
        cabecalho das colunas e TODAS as linhas sao respostas.

    A distincao faz-se pela coluna 27 (horas de estudo semanais): na variante A
    a primeira linha contem texto (o enunciado da pergunta), na variante B
    contem um numero. Esta verificacao evita perder (ou incluir por engano)
    a primeira resposta.
    """
    df_completo = pd.read_excel(caminho_ou_buffer, sheet_name=0)

    if not isinstance(df_completo.columns[0], str) or df_completo.columns[0] in ("1", 1):
        # Colunas ja numeradas -> variante A "classica".
        header = df_completo.iloc[0]
        dados = df_completo.iloc[1:].copy()
        return header, dados, df_completo.shape[1]

    # Colunas com texto: guardar o texto das perguntas e numerar de 1 a n.
    textos_perguntas = list(df_completo.columns)
    df_completo.columns = range(1, df_completo.shape[1] + 1)
    header = pd.Series(textos_perguntas, index=df_completo.columns)

    # A primeira linha e dados ou e (ainda) o texto das perguntas?
    primeira_hora = pd.to_numeric(df_completo.iloc[0][27], errors="coerce")
    if pd.isna(primeira_hora) and isinstance(df_completo.iloc[0][27], str):
        dados = df_completo.iloc[1:].copy()   # Variante A com colunas renomeadas.
    else:
        dados = df_completo.copy()            # Variante B: tudo sao respostas.
    return header, dados, df_completo.shape[1]


def _excel_de_bytes_zip(conteudo, profundidade=0):
    """
    Recebe os bytes de um ficheiro .zip e devolve o buffer do primeiro Excel
    que encontrar la dentro. Trata o caso de ZIPS ANINHADOS (um .zip dentro de
    outro), que e como o Zenodo devolve o arquivo completo do registo: procura
    em profundidade ate encontrar um ficheiro .xlsx.

    Devolve um objeto de bytes (io.BytesIO) pronto a ser lido pelo pandas, ou
    None se nenhum Excel for encontrado.
    """
    if profundidade > 3:  # Salvaguarda contra aninhamento excessivo.
        return None
    with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo:
        nomes = arquivo.namelist()
        # 1) Ha um Excel diretamente neste nivel?
        xlsx = [n for n in nomes if n.lower().endswith(".xlsx")]
        if xlsx:
            return io.BytesIO(arquivo.read(xlsx[0]))
        # 2) Caso contrario, procurar dentro de zips aninhados.
        for n in nomes:
            if n.lower().endswith(".zip"):
                buffer = _excel_de_bytes_zip(arquivo.read(n), profundidade + 1)
                if buffer is not None:
                    return buffer
    return None


def _descarregar_dados_do_zenodo(api=ZENODO_API):
    """
    Descarrega o conjunto de dados a partir da API do Zenodo.

    Consulta o registo, escolhe o ficheiro de dados (de preferencia um .xlsx;
    caso nao exista, o .zip que o contem) e devolve o buffer do Excel. Usar a
    API em vez de um URL fixo torna o programa independente do numero de versao:
    funciona sempre para a versao mais recente do registo.
    """
    import json

    # Passo 1: obter os metadados do registo (lista de ficheiros e URLs).
    with urllib.request.urlopen(api) as resposta:
        metadados = json.load(resposta)
    ficheiros = metadados.get("files", [])

    # Passo 2: escolher o ficheiro a descarregar. Preferimos um .xlsx direto;
    # se nao houver, usamos o primeiro .zip (que contera o Excel).
    def url_do_ficheiro(f):
        # A estrutura da API pode variar ligeiramente entre versoes do Zenodo.
        return (f.get("links", {}).get("self")
                or f.get("links", {}).get("download"))

    alvo = None
    for f in ficheiros:
        nome = (f.get("key") or f.get("filename") or "").lower()
        if nome.endswith(".xlsx"):
            alvo = f
            break
    if alvo is None:
        for f in ficheiros:
            nome = (f.get("key") or f.get("filename") or "").lower()
            if nome.endswith(".zip"):
                alvo = f
                break
    if alvo is None:
        raise RuntimeError("Nao foi encontrado nenhum ficheiro de dados no "
                           "registo do Zenodo.")

    # Passo 3: descarregar o ficheiro escolhido.
    with urllib.request.urlopen(url_do_ficheiro(alvo)) as resposta:
        conteudo = resposta.read()

    nome_alvo = (alvo.get("key") or alvo.get("filename") or "").lower()
    if nome_alvo.endswith(".xlsx"):
        return io.BytesIO(conteudo)          # Excel direto.
    buffer = _excel_de_bytes_zip(conteudo)   # Procurar Excel dentro do zip.
    if buffer is None:
        raise RuntimeError("O ficheiro descarregado do Zenodo nao contem "
                           "nenhum Excel (.xlsx).")
    return buffer


def carregar_dados(nome_local=NOME_FICHEIRO_LOCAL):
    """
    Carrega o conjunto de dados, tentando duas fontes por esta ordem:

      1. Um ficheiro Excel LOCAL, na mesma pasta que este programa. E o caso
         quando se descarrega o pacote completo do Zenodo (dados + script), que
         e a forma recomendada de reproduzir as analises. Funciona OFFLINE.
      2. Se o ficheiro local nao existir, DESCARREGA os dados do Zenodo
         (registo 10.5281/zenodo.17127602, versao mais recente) atraves da API.

    Esta estrategia torna o programa robusto: funciona offline quando os dados
    estao ao lado do script, e continua a funcionar a partir da internet quando
    so se tem o script.

    Devolve
    -------
    header : pandas.Series      -> texto de cada pergunta.
    dados  : pandas.DataFrame    -> respostas dos estudantes.
    """
    caminho_local = Path(__file__).resolve().parent / nome_local

    if caminho_local.exists():
        # --- Fonte 1: ficheiro local (preferida) ---------------------------
        print(f"A ler o ficheiro local: {caminho_local.name}")
        header, dados, n_colunas = _extrair_dados_de_excel(caminho_local)
    else:
        # --- Fonte 2: descarregar do Zenodo via API ------------------------
        print("Ficheiro local nao encontrado; a descarregar do Zenodo...")
        buffer_excel = _descarregar_dados_do_zenodo()
        header, dados, n_colunas = _extrair_dados_de_excel(buffer_excel)

    # As respostas validas sao as que tem horas de estudo (coluna 27) validas.
    n_validas = pd.to_numeric(dados[27], errors="coerce").notna().sum()
    print(f"Dados carregados: {n_validas} respostas validas, "
          f"{n_colunas} colunas.\n")
    return header, dados


# ---------------------------------------------------------------------------
# 2. CONSTRUCAO DOS QUATRO INDICES
# ---------------------------------------------------------------------------
def construir_indices(dados):
    """
    Constroi os quatro indices centrais do artigo e devolve-os num DataFrame.

    Mapeamento das colunas (validado por reproduzir os KR-20 e as correlacoes
    publicadas):

      - BEM-ESTAR (6 itens): sono(39), alimentacao(40), exercicio(41),
        gestao do stress(42), e dois itens invertidos de cansaco:
        cansaco fisico(43) e cansaco psicologico(44).
      - GESTAO DO TEMPO (3 itens): cronograma(28), prioriza(29), pausas(30).
      - ESTRATEGIAS ONLINE: coluna 32, pergunta de RESPOSTA MULTIPLA.
      - HORAS DE ESTUDO SEMANAIS: coluna 27 (valor numerico direto).

    DECISAO METODOLOGICA (indice online redefinido):
    A pergunta 32 permite selecionar varias praticas, separadas por ";". Duas das
    sete opcoes ("Estudar sozinho" e "Outro") NAO sao estrategias digitais. Na
    versao final do artigo, o indice foi restringido ao NUCLEO de 5 opcoes
    digitais, o que elevou a fiabilidade de KR-20 = .28 para .48.
    """
    # --- Indices por media de itens binarios -------------------------------
    bem_estar = pd.DataFrame({
        "sono":        item_binario(dados, 39),
        "alimentacao": item_binario(dados, 40),
        "exercicio":   item_binario(dados, 41),
        "stress":      item_binario(dados, 42),
        "cansaco_fis": item_binario(dados, 43, inverter=True),
        "cansaco_psi": item_binario(dados, 44, inverter=True),
    }).mean(axis=1)  # O indice e a MEDIA dos itens (varia de 0 a 1).

    gestao_tempo = pd.DataFrame({
        "cronograma": item_binario(dados, 28),
        "prioriza":   item_binario(dados, 29),
        "pausas":     item_binario(dados, 30),
    }).mean(axis=1)

    # --- Indice online (proporcao sobre o nucleo de 5 opcoes digitais) -----
    # Passo 1: descobrir todas as opcoes distintas presentes na coluna 32.
    todas_opcoes = set()
    for valor in dados[32].dropna():
        for opcao in str(valor).split(";"):
            if opcao.strip():
                todas_opcoes.add(opcao.strip())

    # Passo 2: excluir as duas opcoes nao-digitais ("Outro" e "Estudar sozinho")
    # para formar o nucleo de 5 opcoes digitais.
    nucleo_digital = [
        o for o in sorted(todas_opcoes)
        if not o.lower().startswith("outro")
        and "sozinho" not in sem_acentos(o.lower())
    ]

    def proporcao_online(valor):
        """Proporcao de opcoes digitais selecionadas por um estudante (0 a 1)."""
        if pd.isna(valor):
            return np.nan
        selecionadas = [o.strip() for o in str(valor).split(";")
                        if o.strip() in nucleo_digital]
        return len(selecionadas) / len(nucleo_digital)

    estrategias_online = dados[32].apply(proporcao_online)

    # --- Horas de estudo semanais (numerico direto) ------------------------
    horas = pd.to_numeric(dados[27], errors="coerce")

    indices = pd.DataFrame({
        "horas": horas,
        "bem_estar": bem_estar,
        "gestao_tempo": gestao_tempo,
        "online": estrategias_online,
    })
    return indices, nucleo_digital


# ---------------------------------------------------------------------------
# 3. FIABILIDADE (KR-20) DOS INDICES
# ---------------------------------------------------------------------------
def calcular_fiabilidades(dados, nucleo_digital):
    """Calcula e imprime o KR-20 dos tres indices compostos."""
    print("=" * 70)
    print("FIABILIDADE DOS INDICES (KR-20)")
    print("=" * 70)

    m_bem_estar = pd.DataFrame({
        "s39": item_binario(dados, 39), "s40": item_binario(dados, 40),
        "s41": item_binario(dados, 41), "s42": item_binario(dados, 42),
        "s43": item_binario(dados, 43, inverter=True),
        "s44": item_binario(dados, 44, inverter=True),
    })
    print(f"  Bem-estar (6 itens):        KR-20 = {kr20(m_bem_estar):.3f}")

    m_tempo = pd.DataFrame({
        "s28": item_binario(dados, 28), "s29": item_binario(dados, 29),
        "s30": item_binario(dados, 30),
    })
    print(f"  Gestao do tempo (3 itens):  KR-20 = {kr20(m_tempo):.3f}")

    # Cada opcao do nucleo torna-se um item binario: 1 se foi selecionada.
    m_online = pd.DataFrame({
        opcao[:15]: dados[32].apply(
            lambda x: 1 if (pd.notna(x) and opcao in str(x))
            else (0 if pd.notna(x) else np.nan)
        )
        for opcao in nucleo_digital
    })
    print(f"  Estrategias online (5 it.): KR-20 = {kr20(m_online):.3f}")
    print("  NOTA: .48 continua abaixo do limiar convencional de .70; os")
    print("        resultados que dependem deste indice sao exploratorios.\n")


# ---------------------------------------------------------------------------
# 4. ESTATISTICAS DESCRITIVAS (TABELA 4)
# ---------------------------------------------------------------------------
def tabela_descritivas(indices):
    """Reproduz a Tabela 4: M, DP, minimo, quartis e maximo de cada indice."""
    print("=" * 70)
    print("TABELA 4 - ESTATISTICAS DESCRITIVAS (escala 0-1)")
    print("=" * 70)
    d = indices.dropna()
    for coluna, etiqueta in [("bem_estar", "Bem-estar"),
                             ("gestao_tempo", "Gestao do tempo"),
                             ("online", "Estrategias online")]:
        s = d[coluna]
        print(f"  {etiqueta:20} M={s.mean():.2f} DP={s.std():.2f} "
              f"Min={s.min():.2f} Q1={s.quantile(.25):.2f} "
              f"Med={s.median():.2f} Q3={s.quantile(.75):.2f} Max={s.max():.2f}")
    print()


# ---------------------------------------------------------------------------
# 5. CORRELACOES DE SPEARMAN (TABELA 5 E FIGURA 3)
# ---------------------------------------------------------------------------
def correlacoes_spearman(indices):
    """
    Calcula as correlacoes de Spearman entre todos os pares de variaveis e
    desenha a matriz (Figura 3).

    Usamos Spearman (baseado em ordens) em vez de Pearson porque os indices nao
    sao normais e algumas relacoes podem ser monotonas mas nao lineares.
    """
    print("=" * 70)
    print("TABELA 5 / FIGURA 3 - CORRELACOES DE SPEARMAN")
    print("=" * 70)
    d = indices.dropna()
    colunas = ["horas", "bem_estar", "gestao_tempo", "online"]
    etiquetas = ["Horas de estudo", "Bem-estar", "Gestao do tempo",
                 "Estrategias online"]

    n = len(colunas)
    rho = np.zeros((n, n))
    pval = np.ones((n, n))
    for i in range(n):
        for j in range(n):
            r, p = stats.spearmanr(d[colunas[i]], d[colunas[j]])
            rho[i, j], pval[i, j] = r, p

    for i in range(n):
        for j in range(i + 1, n):
            estrela = "**" if pval[i, j] < .01 else ("*" if pval[i, j] < .05 else "")
            print(f"  {etiquetas[i]:20} x {etiquetas[j]:20} "
                  f"rho={rho[i, j]:+.2f}{estrela} (p={pval[i, j]:.3f})")

    # --- Figura 3: mapa de calor da matriz de correlacao -------------------
    fig, ax = plt.subplots(figsize=(8, 6.5))
    imagem = ax.imshow(rho, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(n):
        for j in range(n):
            estrela = ("" if i == j else
                       ("**" if pval[i, j] < .01 else
                        ("*" if pval[i, j] < .05 else "")))
            ax.text(j, i, f"{rho[i, j]:.2f}{estrela}",
                    ha="center", va="center", fontsize=11)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(etiquetas, rotation=30, ha="right")
    ax.set_yticklabels(etiquetas)
    barra = fig.colorbar(imagem, ax=ax, shrink=0.8)
    barra.set_label("rho de Spearman")
    plt.tight_layout()
    caminho = PASTA_FIGURAS / "figura3_correlacoes.png"
    plt.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figura 3 gravada em {caminho}]\n")


# ---------------------------------------------------------------------------
# 6. DIFERENCAS POR SEXO (TABELA 6)
# ---------------------------------------------------------------------------
def diferencas_por_sexo(dados, indices):
    """
    Compara masculino vs feminino em cada indice, com o teste de Mann-Whitney
    (nao-parametrico) e o tamanho de efeito delta de Cliff.

    A coluna 7 do questionario contem o sexo ("Masculino"/"Feminino").
    """
    print("=" * 70)
    print("TABELA 7 - DIFERENCAS POR SEXO (Mann-Whitney U e delta de Cliff)")
    print("=" * 70)
    d = indices.copy()
    d["sexo"] = dados[7]
    d = d.dropna(subset=["horas", "bem_estar", "gestao_tempo", "online"])

    masc = d[d.sexo == "Masculino"]
    fem = d[d.sexo == "Feminino"]
    print(f"  (n masculino = {len(masc)}, n feminino = {len(fem)})")

    # CONVENCAO DE APRESENTACAO (fixada para todo o artigo):
    #   - U reportado = o MENOR dos dois valores possiveis de U (a estatistica
    #     de Mann-Whitney pode ser calculada "de cada lado"; U_masc + U_fem =
    #     n_masc * n_fem, e reportar o menor e a convencao classica);
    #   - delta de Cliff com direcao "masculino menos feminino" (delta > 0
    #     significa valores mais altos no grupo masculino).
    for coluna, etiqueta in [("online", "Estrategias online"),
                             ("gestao_tempo", "Gestao do tempo"),
                             ("bem_estar", "Bem-estar")]:
        U_masc, p = stats.mannwhitneyu(masc[coluna], fem[coluna],
                                       alternative="two-sided")
        U_fem = len(masc) * len(fem) - U_masc  # O U "do outro lado".
        U_reportado = min(U_masc, U_fem)
        delta = cliff_delta(masc[coluna], fem[coluna])
        magnitude = ("medio" if abs(delta) >= .33 else
                     ("pequeno" if abs(delta) >= .147 else "negligivel"))
        print(f"  {etiqueta:20} U={U_reportado:.1f} p={p:.3f} "
              f"delta={delta:+.2f} ({magnitude})"
              f"   [U_masc={U_masc:.1f}, U_fem={U_fem:.1f}]")
    print()


# ---------------------------------------------------------------------------
# 7. REGRESSAO ROBUSTA (TABELA 8)
# ---------------------------------------------------------------------------
def regressao_robusta(indices):
    """
    Estima a regressao das horas de estudo sobre os tres indices psicossociais,
    COM e SEM os dois casos atipicos, usando o estimador robusto de Huber.

    PORQUE REGRESSAO ROBUSTA?
    Dois estudantes reportaram cargas extremas (70 e 75 horas) com bem-estar
    minimo. A OLS classica e muito sensivel a estes pontos. O estimador M de
    Huber atribui-lhes menos peso, sendo mais fiavel perante atipicos.

    CRITERIO OBJETIVO PARA OS ATIPICOS (regra de Tukey para valores extremos):
    Um valor e "extremo" se ultrapassar Q3 + 3*IQR. Aplicado as horas, este
    limiar (62h) isola EXATAMENTE os dois casos (70 e 75), sem arbitrariedade.

    SOBRE O R2:
    O estimador de Huber nao produz um R2 padrao. Reportamos, apenas como
    indicacao AUXILIAR do ajuste, o R2 de uma OLS sobre os mesmos preditores.
    Este valor descreve o ajuste OLS, nao o do modelo robusto.
    """
    print("=" * 70)
    print("TABELA 6 - REGRESSAO ROBUSTA (Huber) DAS HORAS DE ESTUDO")
    print("=" * 70)
    d = indices.dropna()

    def ajustar(subconjunto, etiqueta):
        X = sm.add_constant(subconjunto[["bem_estar", "gestao_tempo", "online"]])
        y = subconjunto["horas"]
        modelo = sm.RLM(y, X, M=sm.robust.norms.HuberT()).fit()  # Modelo robusto.
        r2_ols = sm.OLS(y, X).fit().rsquared                     # R2 auxiliar OLS.

        print(f"\n  {etiqueta} (n = {len(subconjunto)}):")
        print(f"    {'Preditor':22}{'B':>8}{'EP':>7}{'p':>8}   IC 95%")
        nomes = {"const": "Intercepto", "bem_estar": "Bem-estar",
                 "gestao_tempo": "Gestao do tempo", "online": "Estrategias online"}
        for chave in ["const", "bem_estar", "gestao_tempo", "online"]:
            B = modelo.params[chave]
            EP = modelo.bse[chave]
            p = modelo.pvalues[chave]
            lo, hi = modelo.conf_int().loc[chave]
            print(f"    {nomes[chave]:22}{B:8.2f}{EP:7.2f}{p:8.3f}   "
                  f"[{lo:6.2f}, {hi:6.2f}]")
        print(f"    R2 auxiliar (OLS, mesmos preditores) = {r2_ols:.3f}")

    ajustar(d, "COM os dois casos atipicos")
    ajustar(d[d.horas < 70], "SEM os dois casos atipicos (regra de Tukey)")
    print()


# ---------------------------------------------------------------------------
# 8. ANALISE DE AGRUPAMENTO (FIGURAS 5a E 5b)
# ---------------------------------------------------------------------------
def analise_agrupamento(indices):
    """
    Executa o k-means sobre os 67 estudantes nao-atipicos, valida a solucao de
    dois grupos e produz duas figuras: o grafico de cotovelo (5a) e a projecao
    PCA dos grupos (5b).

    PORQUE SEPARAR OS ATIPICOS?
    O k-means minimiza distancias quadradas e e muito sensivel a valores
    extremos. Os dois casos de 70-75h formariam um "grupo" artificial de dois
    pontos. Analisamo-los a parte e agrupamos os restantes 67.

    VALIDACAO DA SOLUCAO:
      - Silhueta: quao bem cada ponto encaixa no seu grupo (mais alto = melhor).
      - Estabilidade por bootstrap (ARI): reamostrar e ver se os grupos se mantem.
      - Concordancia com agrupamento hierarquico (Ward), como verificacao cruzada.
    """
    print("=" * 70)
    print("AGRUPAMENTO (k-means) - FIGURAS 5a e 5b")
    print("=" * 70)
    d = indices.dropna().reset_index(drop=True)
    sem_atipicos = d[d.horas < 70].reset_index(drop=True)

    variaveis = ["bem_estar", "gestao_tempo", "online", "horas"]
    X = StandardScaler().fit_transform(sem_atipicos[variaveis])

    # --- Solucao principal: k = 2 sobre os 67 estudantes nao-atipicos -------
    # n_init=25: o k-means e executado 25 vezes com centros iniciais diferentes
    # e fica a melhor solucao. Com n_init baixo (p. ex. 10) o algoritmo pode
    # parar num minimo local e os indicadores mudam ligeiramente; com 25 ou
    # mais inicializacoes a solucao aqui e estavel (verificado ate n_init=100).
    km = KMeans(n_clusters=2, n_init=25, random_state=RANDOM_STATE).fit(X)
    silhueta = silhouette_score(X, km.labels_)
    ch = calinski_harabasz_score(X, km.labels_)
    ward = AgglomerativeClustering(n_clusters=2, linkage="ward").fit_predict(X)
    ari_ward = adjusted_rand_score(km.labels_, ward)

    # --- Solucao de comparacao: k = 3 sobre a amostra completa (n = 69) -----
    X_completo = StandardScaler().fit_transform(d[variaveis])
    km3 = KMeans(n_clusters=3, n_init=25, random_state=RANDOM_STATE).fit(X_completo)
    silhueta_k3 = silhouette_score(X_completo, km3.labels_)

    print(f"  Silhueta (k=2, n=67, sem atipicos)  = {silhueta:.4f}")
    print(f"  Silhueta (k=3, n=69, amostra toda)  = {silhueta_k3:.4f}")
    print(f"  Calinski-Harabasz (k=2)             = {ch:.1f}")
    print(f"  Concordancia k-means vs Ward (ARI)  = {ari_ward:.4f}")

    # --- Estabilidade por reamostragem bootstrap ----------------------------
    # PROCEDIMENTO (fixado explicitamente, para reprodutibilidade total):
    #   * 200 reamostragens COM reposicao, do mesmo tamanho da amostra;
    #   * indices sorteados com numpy.random.default_rng(RANDOM_STATE), pelo
    #     que a sequencia de reamostragens e sempre a mesma;
    #   * a padronizacao (z-scores) e refeita DENTRO de cada reamostragem,
    #     porque na pratica um investigador padronizaria a amostra que tem;
    #   * em cada reamostragem, novo k-means (n_init=10, random_state=0);
    #   * a particao da reamostragem e comparada com a solucao original
    #     (restrita aos casos sorteados; observacoes repetidas mantem-se
    #     repetidas, como e proprio do bootstrap) atraves do ARI, que e
    #     invariante a permutacao das etiquetas dos grupos;
    #   * o indicador final e a MEDIA dos 200 ARIs.
    def estabilidade_bootstrap(subconjunto, k, rotulos_originais,
                               n_reamostragens=200):
        gerador = np.random.default_rng(RANDOM_STATE)
        aris = []
        for _ in range(n_reamostragens):
            idx = gerador.choice(len(subconjunto), len(subconjunto),
                                 replace=True)
            Xb = StandardScaler().fit_transform(
                subconjunto.iloc[idx][variaveis])
            rotulos_b = KMeans(n_clusters=k, n_init=10,
                               random_state=0).fit(Xb).labels_
            aris.append(adjusted_rand_score(rotulos_originais[idx], rotulos_b))
        return np.mean(aris), np.std(aris)

    ari_boot_k2, dp_k2 = estabilidade_bootstrap(sem_atipicos, 2, km.labels_)
    ari_boot_k3, dp_k3 = estabilidade_bootstrap(d, 3, km3.labels_)
    print(f"  Estabilidade bootstrap (k=2, n=67)  = ARI medio {ari_boot_k2:.4f}"
          f" (DP {dp_k2:.3f})")
    print(f"  Estabilidade bootstrap (k=3, n=69)  = ARI medio {ari_boot_k3:.4f}"
          f" (DP {dp_k3:.3f})")

    # Caracterizacao dos dois grupos (ordenados por horas medias).
    sem_atipicos = sem_atipicos.copy()
    sem_atipicos["grupo"] = km.labels_
    medias_horas = sem_atipicos.groupby("grupo").horas.mean().sort_values()
    renomear = {medias_horas.index[0]: "Grupo 1 (carga baixa)",
                medias_horas.index[1]: "Grupo 2 (carga alta)"}
    sem_atipicos["grupo_nome"] = sem_atipicos.grupo.map(renomear)

    print("\n  TABELA 8 - Caracterizacao dos grupos (medias nas escalas originais):")
    resumo = sem_atipicos.groupby("grupo_nome").agg(
        n=("horas", "size"), horas=("horas", "mean"),
        bem_estar=("bem_estar", "mean"), gestao_tempo=("gestao_tempo", "mean"),
        online=("online", "mean"))
    print(resumo.round(2).to_string())

    # Os dois casos atipicos sao descritos a parte (nao entraram no k-means).
    atipicos = d[d.horas >= 70]
    print("  Casos atipicos (n=2):"
          f" horas={atipicos.horas.mean():.2f}"
          f" bem_estar={atipicos.bem_estar.mean():.2f}"
          f" gestao_tempo={atipicos.gestao_tempo.mean():.2f}"
          f" online={atipicos.online.mean():.2f}")

    # --- Figura 5a: grafico de cotovelo ------------------------------------
    fig, eixos = plt.subplots(1, 2, figsize=(11, 4.2))
    for eixo, (subconj, titulo) in zip(
            eixos, [(d, "Amostra completa (n=69)"),
                    (sem_atipicos, "Sem atipicos (n=67)")]):
        Xk = StandardScaler().fit_transform(subconj[variaveis])
        inercias = [KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE)
                    .fit(Xk).inertia_ for k in range(1, 7)]
        eixo.plot(range(1, 7), inercias, "o-", color="#2E5A87", lw=2, ms=7)
        eixo.set_xlabel("Numero de grupos (k)")
        eixo.set_ylabel("Soma dos quadrados intra-grupo")
        eixo.set_title(titulo)
        eixo.grid(alpha=0.3)
    plt.tight_layout()
    caminho_5a = PASTA_FIGURAS / "figura5a_cotovelo.png"
    plt.savefig(caminho_5a, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  [Figura 5a gravada em {caminho_5a}]")

    # --- Figura 5b: projecao PCA (calculada sobre os 69) -------------------
    escala = StandardScaler().fit(d[variaveis])
    pca = PCA(n_components=2, random_state=RANDOM_STATE).fit(
        escala.transform(d[variaveis]))
    proj = pca.transform(escala.transform(d[variaveis]))
    var = pca.explained_variance_ratio_ * 100

    d = d.copy()
    d["p1"], d["p2"] = proj[:, 0], proj[:, 1]
    d["atipico"] = d.horas >= 70
    d["categoria"] = "-"
    d.loc[~d.atipico, "categoria"] = sem_atipicos["grupo_nome"].values
    d.loc[d.atipico, "categoria"] = "Casos atipicos"

    cores = {"Grupo 1 (carga baixa)": "#FD8D3C",
             "Grupo 2 (carga alta)": "#6BAED6",
             "Casos atipicos": "#2CA02C"}
    fig, eixo = plt.subplots(figsize=(7.5, 5.4))
    for categoria in cores:
        sub = d[d.categoria == categoria]
        eixo.scatter(sub.p1, sub.p2, c=cores[categoria],
                     label=f"{categoria} (n={len(sub)})", s=55,
                     edgecolor="white", linewidth=0.5,
                     marker="D" if categoria == "Casos atipicos" else "o",
                     zorder=6 if categoria == "Casos atipicos" else 3)
    eixo.set_xlabel(f"PCA 1 ({var[0]:.1f}% da variancia)")
    eixo.set_ylabel(f"PCA 2 ({var[1]:.1f}% da variancia)")
    eixo.legend(title="Agrupamento", frameon=True, loc="lower right",
                fontsize=9, framealpha=0.9)
    eixo.grid(alpha=0.25)
    plt.tight_layout()
    caminho_5b = PASTA_FIGURAS / "figura5b_pca.png"
    plt.savefig(caminho_5b, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figura 5b gravada em {caminho_5b}]\n")


# ---------------------------------------------------------------------------
# 9. FIGURAS DESCRITIVAS DO ARTIGO (FIGURA 2 E FIGURA 4)
# ---------------------------------------------------------------------------
def figura2_boxplots(indices):
    """
    Figura 2 do artigo: diagramas de caixa dos tres indices normalizados.

    Reflete a operacionalizacao final: bem-estar com 6 itens, gestao do tempo
    com 3 itens (o indice so pode tomar os valores 0, 1/3, 2/3 e 1, dai a
    caixa "por degraus") e estrategias online com 5 opcoes digitais.
    """
    d = indices.dropna()
    series = [d["bem_estar"], d["gestao_tempo"], d["online"]]
    etiquetas = ["Well-being", "Time management", "Online academic strategies"]
    cores = ["#9FB2D8", "#FA8B6B", "#66C2A5"]

    fig, eixo = plt.subplots(figsize=(10, 4.2))
    caixas = eixo.boxplot(series, labels=etiquetas, patch_artist=True,
                          medianprops=dict(color="black", lw=2))
    for caixa, cor in zip(caixas["boxes"], cores):
        caixa.set_facecolor(cor)
    eixo.set_ylabel("Normalised score (0-1)")
    eixo.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    caminho = PASTA_FIGURAS / "figura2_boxplots_indices.png"
    plt.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figura 2 gravada em {caminho}]\n")


def figura4_diferencas_sexo(dados, indices):
    """
    Figura 4 do artigo: distribuicao dos tres indices por sexo, com o valor de
    p do teste de Mann-Whitney e o delta de Cliff no titulo de cada painel.

    Os valores sao CALCULADOS aqui (nao copiados), pelo que a figura fica
    automaticamente coerente com a Tabela 7.
    """
    d = indices.copy()
    d["sexo"] = dados[7]
    d = d.dropna(subset=["horas", "bem_estar", "gestao_tempo", "online"])
    masc, fem = d[d.sexo == "Masculino"], d[d.sexo == "Feminino"]

    paineis = [("online", "Academic strategies by gender"),
               ("gestao_tempo", "Time management by gender"),
               ("bem_estar", "Well-being by gender")]
    fig, eixos = plt.subplots(1, 3, figsize=(15, 4.6))
    for eixo, (coluna, titulo) in zip(eixos, paineis):
        _, p = stats.mannwhitneyu(masc[coluna], fem[coluna],
                                  alternative="two-sided")
        delta = cliff_delta(masc[coluna], fem[coluna])
        magnitude = ("medium" if abs(delta) >= .33 else
                     ("small" if abs(delta) >= .147 else "negligible"))
        caixas = eixo.boxplot([masc[coluna], fem[coluna]],
                              labels=[f"Male\n(n={len(masc)})",
                                      f"Female\n(n={len(fem)})"],
                              patch_artist=True,
                              medianprops=dict(color="black", lw=2))
        for caixa, cor in zip(caixas["boxes"], ["#6A8FC7", "#E8A075"]):
            caixa.set_facecolor(cor)
        eixo.set_title(f"{titulo}\nMann-Whitney U: p = {p:.3f} - "
                       f"Cliff's d = {delta:.2f} ({magnitude})", fontsize=10)
        eixo.set_ylabel("Normalised score (0-1)")
        eixo.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    caminho = PASTA_FIGURAS / "figura4_diferencas_sexo.png"
    plt.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figura 4 gravada em {caminho}]\n")


# ---------------------------------------------------------------------------
# 10. ANALISE TEXTUAL DAS RESPOSTAS ABERTAS (SECCAO 3.9 DO ARTIGO)
# ---------------------------------------------------------------------------
# As respostas abertas sao analisadas POR CATEGORIA TEMATICA DEFINIDA A PRIORI,
# isto e, pelos cinco blocos do proprio questionario. Esta opcao substitui o
# agrupamento lexical exploratorio de versoes anteriores: como as categorias
# vem do desenho do instrumento, nao ha nenhum numero de grupos a escolher nem
# a justificar.
#
# O corpus usa APENAS os itens de TEXTO LIVRE. Ficam de fora dois itens de
# formato fechado que pertencem aos mesmos blocos tematicos: a pergunta de
# escolha multipla sobre desafios (coluna 38, cujas opcoes pre-definidas -
# "manter a concentracao", "procrastinacao", "sobrecarga de tarefas" -
# inflacionariam as frequencias com texto que nao e dos estudantes) e a
# pergunta sim/nao sobre pedir ajuda (coluna 51, sem conteudo lexical).

# Mapa: categoria tematica -> colunas de texto livre no questionario.
CATEGORIAS_TEXTO = {
    "Motivations and views":            [58, 59],
    "Self-assessment and strategies":   [35, 37, 55],
    "Challenges and resources":         [48, 49],
    "Interaction and support":          [52],
    "Reflection and final comments":    [65, 66, 67],
}

# Palavras funcionais (stop-words) do portugues, mais um pequeno conjunto de
# palavras funcionais inglesas (alguns estudantes responderam em ingles).
# A lista esta no proprio programa para nao depender de pacotes externos.
STOPWORDS_PT = set("""
a as o os um uma uns umas de do da dos das em no na nos nas por pelo pela
pelos pelas com sem sob sobre entre para pra e ou mas que se nao sim ao aos
mais menos muito muitos muita muitas pouco poucos pouca poucas ja tambem so
apenas ate como quando onde quem qual quais cujo cuja eu tu ele ela nos vos
eles elas me te lhe lhes meu minha meus minhas teu tua seus suas seu sua
nosso nossa nossos nossas este esta estes estas esse essa esses essas aquele
aquela isso isto aquilo ser sou es somos sao era eram foi fui foram estar
estou esta estao estava estavam esteve ter tenho tem tinha tinham teve haver
ha havia fazer faco faz fazem fez fiz vou vai vao ir indo ido sido sendo
estado pois porque porem contudo entao assim alem cada qualquer outro outra
outros outras depois antes durante sempre nunca vezes vez talvez ainda coisa
coisas forma modo maneira exemplo parte partes lo la los las num numa nuns
numas dum duma neste nesta nestes nestas nesse nessa nesses nessas naquele
naquela mim ti si consigo comigo contigo atraves
and the that with for this are was have has not but they them their there
what which when where how all any can could would should will
""".split())


def _tokenizar(texto):
    """
    Divide uma resposta em palavras (tokens) para a analise lexical.

    Passos: minusculas; remover pontuacao; separar por espacos; descartar
    palavras com menos de 3 letras, numeros e stop-words. A comparacao com a
    lista de stop-words e feita SEM acentos ("tambem" com e sem acento sao a
    mesma palavra), mas o token conserva a grafia original, para a leitura ser
    natural. Tal como na versao anterior do artigo, nao se aplica stemming nem
    lematizacao.
    """
    texto = str(texto).lower()
    texto = re.sub(r"[^\w\s\u00e1\u00e0\u00e2\u00e3\u00e9\u00ea\u00ed\u00f3\u00f4\u00f5\u00fa\u00fc\u00e7-]", " ", texto)
    tokens = []
    for palavra in texto.split():
        palavra = palavra.strip("-")
        if (len(palavra) >= 3 and not palavra.isdigit()
                and sem_acentos(palavra) not in STOPWORDS_PT):
            tokens.append(palavra)
    return tokens


def _g2_verosimilhanca(freq_dentro, freq_fora, total_dentro, total_fora):
    """
    Razao de log-verosimilhanca G2 (Dunning, 1993) para "keyness": mede se um
    termo e mais frequente numa categoria do que no resto do corpus, alem do
    que o acaso explicaria. Quanto maior o G2, mais caracteristico o termo.
    Usa-se aqui como ORDENACAO DESCRITIVA, nao como teste formal (sem valores
    de p nem correcao para comparacoes multiplas), tal como no texto do artigo.
    """
    total = total_dentro + total_fora
    esperado_dentro = total_dentro * (freq_dentro + freq_fora) / total
    esperado_fora = total_fora * (freq_dentro + freq_fora) / total
    g2 = 0.0
    if freq_dentro > 0:
        g2 += freq_dentro * np.log(freq_dentro / esperado_dentro)
    if freq_fora > 0:
        g2 += freq_fora * np.log(freq_fora / esperado_fora)
    return 2 * g2


def analise_textual(header, dados):
    """
    Reproduz a Seccao 3.9 do artigo: analise lexical das respostas abertas
    por categoria tematica a priori.

      1. Constroi o corpus a partir dos 11 itens de texto livre (uma "resposta"
         = o texto de um estudante a um item), ignorando respostas vazias ou
         sem conteudo ("sim", "nao", "-").
      2. Conta as frequencias globais dos termos e gera a nuvem de palavras
         (Figura 6), se o pacote `wordcloud` estiver instalado.
      3. Para cada categoria, identifica os termos mais caracteristicos
         (maior G2 face ao resto do corpus), exigindo frequencia minima de 4
         ocorrencias na categoria (Tabela 10).
    """
    from collections import Counter

    print("=" * 70)
    print("SECCAO 3.9 - ANALISE TEXTUAL POR CATEGORIA TEMATICA")
    print("=" * 70)

    # --- 1. Corpus ----------------------------------------------------------
    respostas = []   # lista de tuplos (categoria, texto)
    for categoria, colunas in CATEGORIAS_TEXTO.items():
        for coluna in colunas:
            for valor in dados[coluna].dropna():
                texto = str(valor).strip()
                if texto and sem_acentos(texto.lower()) not in (
                        "sim", "nao", "-", "n/a", "na"):
                    respostas.append((categoria, texto))
    corpus = pd.DataFrame(respostas, columns=["categoria", "texto"])
    corpus["tokens"] = corpus["texto"].apply(_tokenizar)
    print(f"  Corpus: {len(corpus)} respostas nao vazias, "
          f"{len(CATEGORIAS_TEXTO)} categorias.")
    print(corpus["categoria"].value_counts().to_string())

    # --- 2. Frequencias globais e Figura 6 (nuvem de palavras) --------------
    frequencias = Counter(t for tokens in corpus["tokens"] for t in tokens)
    print("\n  Termos mais frequentes no corpus (top 15):")
    for termo, freq in frequencias.most_common(15):
        print(f"    {termo:20} {freq}")

    try:
        from wordcloud import WordCloud
        nuvem = WordCloud(width=1400, height=800, background_color="white",
                          colormap="viridis", random_state=RANDOM_STATE,
                          max_words=100).generate_from_frequencies(frequencias)
        fig, eixo = plt.subplots(figsize=(11, 6.5))
        eixo.imshow(nuvem, interpolation="bilinear")
        eixo.axis("off")
        plt.tight_layout()
        caminho = PASTA_FIGURAS / "figura6_nuvem_palavras.png"
        plt.savefig(caminho, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\n  [Figura 6 gravada em {caminho}]")
    except ImportError:
        print("\n  [Pacote 'wordcloud' nao instalado; a Figura 6 nao foi "
              "gerada. Instale com: pip install wordcloud]")

    # --- 3. Termos caracteristicos por categoria (Tabela 10) ----------------
    print("\n  TABELA 10 - Termos mais caracteristicos de cada categoria")
    print("  (razao de verosimilhanca G2 vs. resto do corpus; freq. minima 4)")
    linhas_tabela = []
    for categoria in CATEGORIAS_TEXTO:
        dentro = Counter(t for tokens in
                         corpus.loc[corpus.categoria == categoria, "tokens"]
                         for t in tokens)
        fora = Counter(t for tokens in
                       corpus.loc[corpus.categoria != categoria, "tokens"]
                       for t in tokens)
        total_dentro, total_fora = sum(dentro.values()), sum(fora.values())

        candidatos = []
        for termo, freq in dentro.items():
            if freq < 4:
                continue  # termos raros nao sao informativos
            # So interessam termos SOBRE-representados na categoria.
            if freq / total_dentro <= fora.get(termo, 0) / total_fora:
                continue
            g2 = _g2_verosimilhanca(freq, fora.get(termo, 0),
                                    total_dentro, total_fora)
            candidatos.append((termo, freq, g2))
        candidatos.sort(key=lambda x: -x[2])

        top5 = candidatos[:5]
        termos_str = ", ".join(f"{t} (f={f}, G2={g:.1f})" for t, f, g in top5)
        print(f"    {categoria}:")
        print(f"      {termos_str}")
        for t, f, g in top5:
            linhas_tabela.append({"categoria": categoria, "termo": t,
                                  "frequencia": f, "G2": round(g, 1)})

    tabela10 = pd.DataFrame(linhas_tabela)
    caminho_csv = PASTA_FIGURAS / "tabela10_termos_por_categoria.csv"
    tabela10.to_csv(caminho_csv, index=False)
    print(f"\n  [Tabela 10 gravada em {caminho_csv}]\n")


# ---------------------------------------------------------------------------
# 11. FUNCAO PRINCIPAL - orquestra toda a analise pela ordem do artigo
# ---------------------------------------------------------------------------
def main():
    """Executa a analise completa, do carregamento dos dados as figuras."""
    header, dados = carregar_dados()
    indices, nucleo_digital = construir_indices(dados)

    calcular_fiabilidades(dados, nucleo_digital)
    tabela_descritivas(indices)
    figura2_boxplots(indices)
    correlacoes_spearman(indices)
    regressao_robusta(indices)
    diferencas_por_sexo(dados, indices)
    figura4_diferencas_sexo(dados, indices)
    analise_agrupamento(indices)
    analise_textual(header, dados)

    print("=" * 70)
    print("ANALISE CONCLUIDA. As figuras estao na pasta ./figuras/")
    print("=" * 70)


# main() so corre quando o ficheiro e executado diretamente (nao ao importar).
if __name__ == "__main__":
    main()
