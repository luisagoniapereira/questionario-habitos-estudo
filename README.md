# Reprodução das análises quantitativas

Materiais de reprodutibilidade do estudo **"Study Engagement, Self-Regulation
and Well-Being in Hybrid Higher Education"** (Universidade Atlântica, n = 69).

Este pacote contém o conjunto de dados e um programa em Python que reproduz,
do princípio ao fim, todas as análises quantitativas descritas no artigo.

---

## Conteúdo do registo

| Ficheiro | Descrição |
|---|---|
| `Questionario_Limpo.xlsx` | Dados do questionário (respostas anonimizadas). |
| `reproducao_analise.py` | Programa que reproduz todas as análises quantitativas. |
| `README.md` | Este ficheiro. |

> Nota sobre a estrutura do Excel: a **primeira linha** contém o texto das
> perguntas (não dados); as respostas começam na segunda linha. As colunas
> estão numeradas de 1 a 67. O programa trata isto automaticamente.

---

## O que o programa reproduz

Seguindo a ordem do artigo, o programa calcula e apresenta:

1. A fiabilidade (KR-20) dos três índices compostos.
2. As estatísticas descritivas dos índices (Tabela 4 e Figura 2).
3. As correlações de Spearman entre os índices e as horas de estudo
   (Tabela 5 e Figura 3).
4. A regressão robusta de Huber das horas de estudo, com e sem os dois casos
   atípicos (Tabela 6).
5. As diferenças por sexo, com o teste de Mann-Whitney e o delta de Cliff
   (Tabela 7 e Figura 4).
6. A análise de agrupamento (k-means) com validação por silhueta, reamostragem
   bootstrap com semente fixa e concordância com o agrupamento hierárquico de
   Ward (Tabela 8, Figuras 5a e 5b).
7. A análise lexical das respostas abertas, por categoria temática definida
   a priori no questionário: frequências de termos (Figura 6) e termos
   caracteristicamente associados a cada categoria, ordenados pela razão de
   log-verosimilhança G2 (Tabela 10).

As figuras são gravadas na pasta `./figuras/`; os resultados numéricos são
impressos no ecrã.

**Âmbito.** O programa cobre a componente quantitativa **e** a análise textual
das respostas abertas (Secção 3.9 do artigo). Ambas partem do mesmo ficheiro de
dados, pelo que todos os números e figuras do artigo podem ser reproduzidos com
uma única execução.

---

## Requisitos

- Python 3.9 ou superior (os resultados do artigo foram verificados com
  Python 3.10.12).
- Bibliotecas: `pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`,
  `matplotlib`, `openpyxl` e `wordcloud` (esta última apenas para a Figura 6;
  sem ela, o programa corre na mesma e avisa que a figura não foi gerada).

Instalação das bibliotecas:

```bash
pip install pandas numpy scipy statsmodels scikit-learn matplotlib openpyxl wordcloud
```

O ficheiro `requirements.txt` regista as versões exatas com que os resultados
do artigo foram verificados; para um ambiente equivalente, use:

```bash
pip install -r requirements.txt
```

---

## Como executar

1. Descarregue **todos os ficheiros deste registo** para a mesma pasta
   (em particular, `reproducao_analise.py` e `Questionario_Limpo.xlsx`).
2. Nessa pasta, execute:

```bash
python reproducao_analise.py
```

### Origem dos dados: local ou Zenodo

O programa procura os dados por esta ordem:

1. **Ficheiro local** `Questionario_Limpo.xlsx`, na mesma pasta que o programa
   (é o caso quando se descarrega o pacote completo deste registo). Esta é a
   forma recomendada e funciona **sem ligação à internet**.
2. Se o ficheiro local não for encontrado, o programa **descarrega os dados
   automaticamente do Zenodo** (DOI abaixo) e prossegue.

Assim, o programa funciona tanto com o pacote completo como sozinho.

---

## Reprodutibilidade

Todos os passos com componente aleatória (k-means e reamostragem bootstrap)
usam uma semente fixa (`RANDOM_STATE = 42`), pelo que os resultados são
idênticos em cada execução. Os valores produzidos correspondem aos que constam
no artigo.

---

## Como citar

**Conjunto de dados e código (este registo):**

> Pereira, L. A. G. (2025). *Questionário sobre hábitos de estudo — dados e
> código de reprodução* [Data set e software]. Zenodo.
> https://doi.org/10.5281/zenodo.17127602

O DOI `10.5281/zenodo.17127602` é o *concept DOI*: aponta sempre para a versão
mais recente do registo. Cada versão tem também o seu próprio DOI específico,
apresentado na página do Zenodo; para referências que exijam uma versão exata,
utilize o DOI da versão correspondente.

---

## Licença

Consulte a licença indicada na página do registo no Zenodo.

---

## Contacto

Para questões sobre os dados ou o código, contacte o autor através da página
do registo no Zenodo.
