# Reproduction of the analyses

Reproducibility materials for a study of study habits, self-regulation and
well-being in hybrid higher education (Universidade Atlantica, n = 69). The
associated article is currently under review; its full reference will be
added here upon acceptance.

This package contains the dataset and a Python program that reproduces,
from start to finish, all the analyses reported in the article.

*Versão em português: ver `README_PT.md`.*

---

## Contents

| File | Description |
|---|---|
| `Questionario_Limpo.xlsx` | Questionnaire data (anonymised responses). |
| `reproducao_analise.py` | Program that reproduces all the analyses in the article. |
| `requirements.txt` | Exact versions of the libraries used. |
| `README.md` | This file. |

> Note on the Excel structure: the **first row** contains the question
> wording (not data); responses start on the second row. Columns are
> numbered 1 to 67. The program handles this automatically.

---

## What the program reproduces

Following the order of the article, the program computes and reports:

1. Reliability (KR-20) of the three composite indices.
2. Descriptive statistics of the indices (Table 4 and Figure 2).
3. Spearman correlations between the indices and weekly study hours
   (Figure 3).
4. Huber robust regression of weekly study hours, with and without the two
   atypical cases (Table 5).
5. Differences by sex, using the Mann-Whitney test and Cliff's delta
   (Table 6).
6. The clustering analysis (k-means) with validation by silhouette width,
   fixed-seed bootstrap resampling and agreement with Ward hierarchical
   clustering (Table 7 and the PCA projection in Figure 4).
7. The lexical analysis of the open-ended responses, by a priori thematic
   category: the terms most characteristic of each category, ranked by the
   G2 log-likelihood ratio (Table 9).

Some analyses that were run during the study but not included in the article
are still produced as diagnostics, with no article figure number: the elbow
plot for the cluster count, the by-gender box plots, and a word-cloud overview
of raw term frequencies. No number in the program points to an element that is
absent from the article.

Figures are saved to `./figures/`; numerical results are printed to the
screen.

**Scope.** The program covers both the quantitative component and the
lexical analysis of the open-ended responses (Section 3.9 of the article).
Both start from the same data file, so every number and figure in the
article can be reproduced in a single run.

---

## Requirements

- Python 3.9 or later (the results in the article were verified with
  Python 3.10.12).
- Libraries: `pandas`, `numpy`, `scipy`, `statsmodels`, `scikit-learn`,
  `matplotlib`, `openpyxl` and `wordcloud` (the latter only for the
  diagnostic word cloud; without it, the program still runs and warns that
  the figure was not generated).

Installation:

```bash
pip install pandas numpy scipy statsmodels scikit-learn matplotlib openpyxl wordcloud
```

The file `requirements.txt` records the exact versions used to verify the
results; for an equivalent environment, use:

```bash
pip install -r requirements.txt
```

---

## How to run

1. Download **all the files in this record** to the same folder
   (in particular, `reproducao_analise.py` and `Questionario_Limpo.xlsx`).
2. In that folder, run:

```bash
python reproducao_analise.py
```

### Data source: local file or Zenodo

The program looks for the data in this order:

1. **Local file** `Questionario_Limpo.xlsx`, in the same folder as the
   program (the case when the full package is downloaded). This is the
   recommended route and works **offline**.
2. If the local file is not found, the program **downloads the data
   automatically from Zenodo** (DOI below) and continues.

---

## Reproducibility

Every step with a random component (k-means and bootstrap resampling) uses
a fixed seed (`RANDOM_STATE = 42`), so results are identical on every run
and match the values reported in the article.

---

## Composition of the composite indices

Column numbers refer to `Questionario_Limpo.xlsx`. Each index is the
unweighted mean of its items and ranges from 0 to 1.

| Index | Column | Item (abridged wording) | Coding |
|---|---|---|---|
| Physical and mental well-being (6 items) | 39 | Ensures adequate sleep quality | Yes = 1, No = 0 |
| | 40 | Considers their diet balanced | Yes = 1, No = 0 |
| | 41 | Practises regular exercise or a hobby | Yes = 1, No = 0 |
| | 42 | Manages stress and emotional balance | Yes = 1, No = 0 |
| | 43 | Usually feels physical tiredness | Reverse-coded: Yes = 0, No = 1 |
| | 44 | Usually feels psychological tiredness | Reverse-coded: Yes = 0, No = 1 |
| Time management (3 items) | 28 | Creates study schedules/routines and meets goals | Yes = 1, No = 0 |
| | 29 | Prioritises academic tasks efficiently | Yes = 1, No = 0 |
| | 30 | Uses time efficiently, managing breaks | Yes = 1, No = 0 |
| Online academic strategies (5 options of column 32) | 32 | Summarising texts | Selected = 1 |
| | 32 | Doing exercises | Selected = 1 |
| | 32 | Studying with peers (virtual communities) | Selected = 1 |
| | 32 | Using online resources (videos, manuals, forums) | Selected = 1 |
| | 32 | Creating mind maps / diagrams | Selected = 1 |
| Weekly study hours | 27 | Average weekly study hours | Numeric value |

The options "Estudar sozinho" (studying alone) and "Outro" (other) in
column 32 are not part of the online strategies index because they do not
denote a digital practice; the index is the number of digital options
selected divided by five.

---

## How to cite

**Dataset and code (this record):**

> Mendes, A., Agonia Pereira, L., & Vairinhos, V. (2026). *Student Engagement
> in Hybrid Higher Education: An Exploratory Institutional Case Study - Dataset
> and Reproduction Code* [Data set and software]. Zenodo.
> https://doi.org/10.5281/zenodo.17127601

The DOI `10.5281/zenodo.17127601` is the *concept DOI*: it always points to
the latest version of the record. This is the DOI cited in the associated
article, so the citation always resolves to the most recent version. Each
version also has its own specific DOI, shown on the Zenodo page.

---

## Licence

See the licence shown on the Zenodo record page.

---

## Contact

For questions about the data or the code, contact the author through the
Zenodo record page.
