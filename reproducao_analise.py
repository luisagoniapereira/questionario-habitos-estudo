# -*- coding: utf-8 -*-
"""
=============================================================================
FULL REPRODUCTION OF THE ANALYSES IN THE ARTICLE (QUANTITATIVE AND TEXTUAL)
"Student Engagement in Hybrid Higher Education: An Exploratory Institutional Case Study"
(Universidade Atlantica, n = 69)
=============================================================================

WHAT THIS PROGRAM DOES
----------------------
Reproduces, end to end, all the analyses reported in the article:

  1. Loads the dataset: reads the local file "Questionario_Limpo.xlsx" if it
     sits next to this program, or downloads it from Zenodo otherwise
     (concept DOI 10.5281/zenodo.17127601, which always resolves to the most
     recent version of the record).
  2. Rebuilds the four indices used in the article (well-being, time
     management, online strategies and weekly study hours).
  3. Computes the reliability (KR-20) of each index.
  4. Produces the descriptive statistics (Table 4).
  5. Computes the Spearman correlations (Figure 3).
  6. Fits the robust Huber regression, with and without the atypical cases
     (Table 5).
  7. Compares genders with the Mann-Whitney test and Cliff's delta (Table 6).
  8. Runs the cluster analysis (k-means) with explicit validation:
     silhouette, bootstrap stability and agreement with Ward. The two-group
     structure is shown in the PCA projection (Figure 4) and characterised in
     Table 7. The elbow plot is produced as a diagnostic only and is not shown
     in the article.
  9. Analyses the open-ended responses by a priori thematic category
     (Section 3.9): the most characteristic terms of each category, by G2
     log-likelihood ratio (Table 9). A word-cloud overview of raw term
     frequencies is produced as a diagnostic only and is not shown in the
     article.

NOTE ON FIGURE AND TABLE NUMBERS
--------------------------------
The numbers used here match the published article. Some analyses that were run
during the study but not included in the article (the elbow plot, the by-gender
box plots and the word cloud) are still produced by this script as diagnostics,
but they carry no article figure number, so no number here points to an element
that is absent from the article.

NOTE ON SCOPE
-------------
In this version, the program covers BOTH the quantitative component AND the
lexical analysis of the open-ended responses (Section 3.9). Section 3.9 no
longer depends on Orange Data Mining: the analysis by a priori thematic
categories is reproduced in full by this program, from the same data file.

NOTE ON LANGUAGE
----------------
The questionnaire was administered in Portuguese at a Portuguese university,
so the open-ended responses -- and therefore the terms reported by the lexical
analysis (e.g., "biblioteca", "concentracao") -- are in Portuguese. They are
data, not code, and are reported in the original language, as in the article.

HOW TO RUN
----------
    pip install pandas numpy scipy statsmodels scikit-learn matplotlib openpyxl
    python reproducao_analise.py

Figures are saved to the ./figures/ folder and the numerical results are
printed to the screen.

REPRODUCIBILITY
---------------
The random seed (RANDOM_STATE) is fixed in every stochastic step (k-means and
bootstrap), so the results are identical on every run.

Written with extensive comments because it is intended for teaching contexts:
each block explains not only WHAT it does but WHY it is done this way.
=============================================================================
"""

# ---------------------------------------------------------------------------
# 0. IMPORTS AND GLOBAL CONFIGURATION
# ---------------------------------------------------------------------------
import io                      # Handle the downloaded file in memory.
import re                      # Regular expressions (free-text cleaning).
import zipfile                 # The Zenodo dataset ships compressed in a .zip.
import urllib.request          # Download the file from Zenodo.
import unicodedata             # Strip accents when comparing text.
from pathlib import Path       # Robust file-path handling.

import numpy as np             # Numerical computing (vectors and matrices).
import pandas as pd            # Tabular data structures (DataFrame).
from scipy import stats        # Statistical tests (Spearman, Mann-Whitney).
import statsmodels.api as sm   # Robust regression (Huber estimator) and OLS.

from sklearn.preprocessing import StandardScaler            # Standardisation (z-scores).
from sklearn.cluster import KMeans, AgglomerativeClustering # Clustering.
from sklearn.decomposition import PCA                       # Dimensionality reduction.
from sklearn.metrics import (                               # Validation metrics.
    silhouette_score,
    calinski_harabasz_score,
    adjusted_rand_score,
)

import matplotlib
matplotlib.use("Agg")          # Non-interactive backend (writes files, no display).
import matplotlib.pyplot as plt

# --- Configuration constants (centralised for easy adaptation) --------------
# Zenodo record identifier (the same for all versions; the "records/<id>" API
# resolves to the most recent version). Using the API to discover the data
# file dynamically avoids hard-coding a version number here, and keeps working
# when new versions of the record are published.
# Note: if the file "Questionario_Limpo.xlsx" sits in the same folder as this
# program (as in the complete Zenodo package), the data are read locally and
# the API is never used.
ZENODO_RECORD_ID = "17127601"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
RANDOM_STATE = 42                    # Seed for reproducible results.
LOCAL_DATA_FILENAME = "Questionario_Limpo.xlsx"  # Data file next to the script.
FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)     # Create ./figures/ if it does not exist.


# ---------------------------------------------------------------------------
# LOW-LEVEL HELPER FUNCTIONS
# ---------------------------------------------------------------------------
def strip_accents(text):
    """Remove accents from a string (to compare, e.g., 'sozinho')."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def binary_item(data, column, invert=False):
    """
    Converts a 'Sim'/'Nao' (yes/no) column into 1/0.

    Some items are "reversed": for example, "feels physical tiredness" is a
    NEGATIVE indication of well-being, so a 'Sim' (yes) must count as 0
    (less well-being). The `invert=True` parameter handles those cases.

    NOTE: recognition is tolerant to accents and letter case. In the original
    file the negative answer is "Nao" with a tilde (N-a-tilde-o); rather than
    depending on the exact spelling, each value is normalised (accents removed,
    lower-cased) before being classified. The program therefore works whether
    the file uses "Sim/Nao", "sim/nao" or accented variants.
    """
    def classify(value):
        if pd.isna(value):
            return np.nan
        v = strip_accents(str(value).strip().lower())  # normalise: "Nao" -> "nao"
        if v == "sim":
            return 1
        if v == "nao":
            return 0
        return np.nan  # any other value is treated as missing
    s = data[column].apply(classify)
    return 1 - s if invert else s


def kr20(item_matrix):
    """
    Computes the Kuder-Richardson 20 (KR-20) coefficient.

    KR-20 is the version of Cronbach's alpha for DICHOTOMOUS (0/1) items. It
    measures internal consistency: the extent to which the items of an index
    "move together". It ranges from 0 to 1; values above .70 are conventionally
    regarded as acceptable.

    Formula:  KR-20 = (k / (k-1)) * (1 - sum(p_i * q_i) / total_variance)
      where  k = number of items
             p_i = proportion of 1-responses on item i
             q_i = 1 - p_i
             total_variance = variance of the sum of the items
    """
    items = item_matrix.dropna()
    k = items.shape[1]
    p = items.mean()
    q = 1 - p
    total_variance = items.sum(axis=1).var(ddof=1)  # ddof=1: sample variance.
    return (k / (k - 1)) * (1 - (p * q).sum() / total_variance)


def cliff_delta(a, b):
    """
    Computes Cliff's delta, a NON-parametric effect-size measure.

    It answers the question: "if we draw one value from each group at random,
    what is the probability that one exceeds the other?". It ranges from -1 to
    +1 (0 = no difference). Conventional interpretation: |d| < .147 negligible,
    < .33 small, < .474 medium.

    It is computed from the Mann-Whitney U statistic, which is more efficient
    than counting all pairs directly.
    """
    a, b = np.asarray(a), np.asarray(b)
    n1, n2 = len(a), len(b)
    U, _ = stats.mannwhitneyu(a, b, alternative="two-sided")
    return (2 * U) / (n1 * n2) - 1


# ---------------------------------------------------------------------------
# 1. LOADING THE DATA (local file next to the script, or Zenodo)
# ---------------------------------------------------------------------------
def _extract_data_from_excel(path_or_buffer):
    """
    Reads the Excel file and returns (header, data), where `header` is a
    Series with the TEXT of each question and `data` is the DataFrame of
    responses, with columns numbered 1 to 67.

    The data file has circulated in TWO variants, and the program accepts both:

      Variant A (Zenodo record): the columns are already numbered 1 to 67 and
        the FIRST row holds the text of the questions; responses start on the
        second row.
      Variant B (working file): the question text is in the column headers
        themselves and ALL rows are responses.

    The distinction is made through column 27 (weekly study hours): in variant
    A the first row holds text (the question wording), in variant B it holds a
    number. This check avoids losing (or mistakenly including) the first
    response.
    """
    df_full = pd.read_excel(path_or_buffer, sheet_name=0)

    if not isinstance(df_full.columns[0], str) or df_full.columns[0] in ("1", 1):
        # Columns already numbered -> "classic" variant A.
        header = df_full.iloc[0]
        data = df_full.iloc[1:].copy()
        return header, data, df_full.shape[1]

    # Text column headers: keep the question text and number columns 1..n.
    question_texts = list(df_full.columns)
    df_full.columns = range(1, df_full.shape[1] + 1)
    header = pd.Series(question_texts, index=df_full.columns)

    # Is the first row data, or (still) the question text?
    first_hours = pd.to_numeric(df_full.iloc[0][27], errors="coerce")
    if pd.isna(first_hours) and isinstance(df_full.iloc[0][27], str):
        data = df_full.iloc[1:].copy()   # Variant A with renamed columns.
    else:
        data = df_full.copy()            # Variant B: everything is responses.
    return header, data, df_full.shape[1]


def _excel_from_zip_bytes(content, depth=0):
    """
    Takes the bytes of a .zip file and returns the buffer of the first Excel
    file found inside it. Handles NESTED ZIPS (a .zip inside another), which
    is how Zenodo returns the full archive of a record: it searches in depth
    until it finds an .xlsx file.

    Returns a bytes object (io.BytesIO) ready to be read by pandas, or None
    if no Excel file is found.
    """
    if depth > 3:  # Safeguard against excessive nesting.
        return None
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        # 1) Is there an Excel file directly at this level?
        xlsx = [n for n in names if n.lower().endswith(".xlsx")]
        if xlsx:
            return io.BytesIO(archive.read(xlsx[0]))
        # 2) Otherwise, search inside nested zips.
        for n in names:
            if n.lower().endswith(".zip"):
                buffer = _excel_from_zip_bytes(archive.read(n), depth + 1)
                if buffer is not None:
                    return buffer
    return None


def _download_data_from_zenodo(api=ZENODO_API):
    """
    Downloads the dataset through the Zenodo API.

    Queries the record, picks the data file (preferably an .xlsx; otherwise
    the .zip that contains it) and returns the Excel buffer. Using the API
    instead of a fixed URL makes the program independent of the version
    number: it always works for the most recent version of the record.
    """
    import json

    # Step 1: fetch the record metadata (list of files and URLs).
    with urllib.request.urlopen(api) as response:
        metadata = json.load(response)
    files = metadata.get("files", [])

    # Step 2: pick the file to download. We prefer a direct .xlsx; if there is
    # none, we take the first .zip (which will contain the Excel file).
    def file_url(f):
        # The API structure can vary slightly across Zenodo versions.
        return (f.get("links", {}).get("self")
                or f.get("links", {}).get("download"))

    target = None
    for f in files:
        name = (f.get("key") or f.get("filename") or "").lower()
        if name.endswith(".xlsx"):
            target = f
            break
    if target is None:
        for f in files:
            name = (f.get("key") or f.get("filename") or "").lower()
            if name.endswith(".zip"):
                target = f
                break
    if target is None:
        raise RuntimeError("No data file was found in the Zenodo record.")

    # Step 3: download the chosen file.
    with urllib.request.urlopen(file_url(target)) as response:
        content = response.read()

    target_name = (target.get("key") or target.get("filename") or "").lower()
    if target_name.endswith(".xlsx"):
        return io.BytesIO(content)          # Direct Excel file.
    buffer = _excel_from_zip_bytes(content)  # Look for the Excel inside the zip.
    if buffer is None:
        raise RuntimeError("The file downloaded from Zenodo does not contain "
                           "any Excel (.xlsx) file.")
    return buffer


def load_data(local_name=LOCAL_DATA_FILENAME):
    """
    Loads the dataset, trying two sources in this order:

      1. A LOCAL Excel file, in the same folder as this program. This is the
         case when the complete Zenodo package (data + script) is downloaded,
         which is the recommended way to reproduce the analyses. Works OFFLINE.
      2. If the local file does not exist, DOWNLOADS the data from Zenodo
         (concept record 10.5281/zenodo.17127601, most recent version) through
         the API.

    This strategy makes the program robust: it works offline when the data sit
    next to the script, and still works over the internet when only the script
    is available.

    Returns
    -------
    header : pandas.Series      -> text of each question.
    data   : pandas.DataFrame    -> the students' responses.
    """
    local_path = Path(__file__).resolve().parent / local_name

    if local_path.exists():
        # --- Source 1: local file (preferred) ------------------------------
        print(f"Reading local file: {local_path.name}")
        header, data, n_columns = _extract_data_from_excel(local_path)
    else:
        # --- Source 2: download from Zenodo through the API ----------------
        print("Local file not found; downloading from Zenodo...")
        excel_buffer = _download_data_from_zenodo()
        header, data, n_columns = _extract_data_from_excel(excel_buffer)

    # Valid responses are those with valid study hours (column 27).
    n_valid = pd.to_numeric(data[27], errors="coerce").notna().sum()
    print(f"Data loaded: {n_valid} valid responses, "
          f"{n_columns} columns.\n")
    return header, data


# ---------------------------------------------------------------------------
# 2. BUILDING THE FOUR INDICES
# ---------------------------------------------------------------------------
def build_indices(data):
    """
    Builds the four central indices of the article and returns them in a
    DataFrame.

    Column mapping (validated by reproducing the published KR-20 values and
    correlations):

      - WELL-BEING (6 items): sleep(39), diet(40), exercise(41),
        stress management(42), and two reversed tiredness items:
        physical tiredness(43) and psychological tiredness(44).
      - TIME MANAGEMENT (3 items): schedule(28), prioritises(29), breaks(30).
      - ONLINE STRATEGIES: column 32, a MULTIPLE-RESPONSE question.
      - WEEKLY STUDY HOURS: column 27 (direct numeric value).

    METHODOLOGICAL DECISION (redefined online index):
    Question 32 allows selecting several practices, separated by ";". Two of
    the seven options ("Estudar sozinho" / studying alone, and "Outro" / other)
    are NOT digital strategies. In the final version of the article the index
    was restricted to the CORE of 5 digital options, which raised the
    reliability from KR-20 = .28 to .48.
    """
    # --- Indices as means of binary items ----------------------------------
    well_being = pd.DataFrame({
        "sleep":          binary_item(data, 39),
        "diet":           binary_item(data, 40),
        "exercise":       binary_item(data, 41),
        "stress":         binary_item(data, 42),
        "tired_physical": binary_item(data, 43, invert=True),
        "tired_psych":    binary_item(data, 44, invert=True),
    }).mean(axis=1)  # The index is the MEAN of the items (ranges 0 to 1).

    time_management = pd.DataFrame({
        "schedule":    binary_item(data, 28),
        "prioritises": binary_item(data, 29),
        "breaks":      binary_item(data, 30),
    }).mean(axis=1)

    # --- Online index (proportion over the core of 5 digital options) ------
    # Step 1: discover all distinct options present in column 32.
    all_options = set()
    for value in data[32].dropna():
        for option in str(value).split(";"):
            if option.strip():
                all_options.add(option.strip())

    # Step 2: exclude the two non-digital options ("Outro" and "Estudar
    # sozinho") to form the core of 5 digital options.
    digital_core = [
        o for o in sorted(all_options)
        if not o.lower().startswith("outro")
        and "sozinho" not in strip_accents(o.lower())
    ]

    def online_proportion(value):
        """Proportion of digital options selected by a student (0 to 1)."""
        if pd.isna(value):
            return np.nan
        selected = [o.strip() for o in str(value).split(";")
                    if o.strip() in digital_core]
        return len(selected) / len(digital_core)

    online_strategies = data[32].apply(online_proportion)

    # --- Weekly study hours (direct numeric value) --------------------------
    hours = pd.to_numeric(data[27], errors="coerce")

    indices = pd.DataFrame({
        "hours": hours,
        "well_being": well_being,
        "time_management": time_management,
        "online": online_strategies,
    })
    return indices, digital_core


# ---------------------------------------------------------------------------
# 3. RELIABILITY (KR-20) OF THE INDICES
# ---------------------------------------------------------------------------
def compute_reliabilities(data, digital_core):
    """Computes and prints the KR-20 of the three composite indices."""
    print("=" * 70)
    print("RELIABILITY OF THE INDICES (KR-20)")
    print("=" * 70)

    m_well_being = pd.DataFrame({
        "s39": binary_item(data, 39), "s40": binary_item(data, 40),
        "s41": binary_item(data, 41), "s42": binary_item(data, 42),
        "s43": binary_item(data, 43, invert=True),
        "s44": binary_item(data, 44, invert=True),
    })
    print(f"  Well-being (6 items):        KR-20 = {kr20(m_well_being):.3f}")

    m_time = pd.DataFrame({
        "s28": binary_item(data, 28), "s29": binary_item(data, 29),
        "s30": binary_item(data, 30),
    })
    print(f"  Time management (3 items):   KR-20 = {kr20(m_time):.3f}")

    # Each option of the core becomes a binary item: 1 if it was selected.
    m_online = pd.DataFrame({
        option[:15]: data[32].apply(
            lambda x: 1 if (pd.notna(x) and option in str(x))
            else (0 if pd.notna(x) else np.nan)
        )
        for option in digital_core
    })
    print(f"  Online strategies (5 items): KR-20 = {kr20(m_online):.3f}")
    print("  NOTE: .48 remains below the conventional .70 threshold; results")
    print("        that depend on this index are exploratory.\n")


# ---------------------------------------------------------------------------
# 4. DESCRIPTIVE STATISTICS (TABLE 4)
# ---------------------------------------------------------------------------
def descriptive_table(indices):
    """Reproduces Table 4: M, SD, minimum, quartiles and maximum of each index."""
    print("=" * 70)
    print("TABLE 4 - DESCRIPTIVE STATISTICS (0-1 scale)")
    print("=" * 70)
    d = indices.dropna()
    for column, label in [("well_being", "Well-being"),
                          ("time_management", "Time management"),
                          ("online", "Online strategies")]:
        s = d[column]
        print(f"  {label:20} M={s.mean():.2f} SD={s.std():.2f} "
              f"Min={s.min():.2f} Q1={s.quantile(.25):.2f} "
              f"Med={s.median():.2f} Q3={s.quantile(.75):.2f} Max={s.max():.2f}")
    print()


# ---------------------------------------------------------------------------
# 5. SPEARMAN CORRELATIONS (FIGURE 3)
# ---------------------------------------------------------------------------
def spearman_correlations(indices):
    """
    Computes the Spearman correlations between all pairs of variables and
    draws the matrix (Figure 3).

    Spearman (rank-based) is used instead of Pearson because the indices are
    not normally distributed and some relationships may be monotonic but not
    linear.
    """
    print("=" * 70)
    print("FIGURE 3 - SPEARMAN CORRELATIONS")
    print("=" * 70)
    d = indices.dropna()
    columns = ["hours", "well_being", "time_management", "online"]
    labels = ["Study hours", "Well-being", "Time management",
              "Online strategies"]

    n = len(columns)
    rho = np.zeros((n, n))
    pval = np.ones((n, n))
    for i in range(n):
        for j in range(n):
            r, p = stats.spearmanr(d[columns[i]], d[columns[j]])
            rho[i, j], pval[i, j] = r, p

    for i in range(n):
        for j in range(i + 1, n):
            star = "**" if pval[i, j] < .01 else ("*" if pval[i, j] < .05 else "")
            print(f"  {labels[i]:20} x {labels[j]:20} "
                  f"rho={rho[i, j]:+.2f}{star} (p={pval[i, j]:.3f})")

    # --- Figure 3: heatmap of the correlation matrix -----------------------
    fig, ax = plt.subplots(figsize=(8, 6.5))
    image = ax.imshow(rho, cmap="RdBu_r", vmin=-1, vmax=1)
    for i in range(n):
        for j in range(n):
            star = ("" if i == j else
                    ("**" if pval[i, j] < .01 else
                     ("*" if pval[i, j] < .05 else "")))
            ax.text(j, i, f"{rho[i, j]:.2f}{star}",
                    ha="center", va="center", fontsize=11)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_yticklabels(labels)
    bar = fig.colorbar(image, ax=ax, shrink=0.8)
    bar.set_label("Spearman's rho")
    plt.tight_layout()
    path = FIGURES_DIR / "figure3_correlation_matrix.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 3 saved to {path}]\n")


# ---------------------------------------------------------------------------
# 6. GENDER DIFFERENCES (TABLE 6)
# ---------------------------------------------------------------------------
def gender_differences(data, indices):
    """
    Compares male vs female students on each index, with the Mann-Whitney test
    (non-parametric) and the Cliff's delta effect size.

    Column 7 of the questionnaire holds the gender ("Masculino"/"Feminino").
    """
    print("=" * 70)
    print("TABLE 6 - GENDER DIFFERENCES (Mann-Whitney U and Cliff's delta)")
    print("=" * 70)
    d = indices.copy()
    d["gender"] = data[7]
    d = d.dropna(subset=["hours", "well_being", "time_management", "online"])

    male = d[d.gender == "Masculino"]
    female = d[d.gender == "Feminino"]
    print(f"  (n male = {len(male)}, n female = {len(female)})")

    # REPORTING CONVENTION (fixed for the whole article):
    #   - reported U = the SMALLER of the two possible U values (the
    #     Mann-Whitney statistic can be computed "from either side";
    #     U_male + U_female = n_male * n_female, and reporting the smaller one
    #     is the classic convention);
    #   - Cliff's delta with direction "male minus female" (delta > 0 means
    #     higher values in the male group).
    for column, label in [("online", "Online strategies"),
                          ("time_management", "Time management"),
                          ("well_being", "Well-being")]:
        U_male, p = stats.mannwhitneyu(male[column], female[column],
                                       alternative="two-sided")
        U_female = len(male) * len(female) - U_male  # The U "from the other side".
        U_reported = min(U_male, U_female)
        delta = cliff_delta(male[column], female[column])
        magnitude = ("medium" if abs(delta) >= .33 else
                     ("small" if abs(delta) >= .147 else "negligible"))
        print(f"  {label:20} U={U_reported:.1f} p={p:.3f} "
              f"delta={delta:+.2f} ({magnitude})"
              f"   [U_male={U_male:.1f}, U_female={U_female:.1f}]")
    print()


# ---------------------------------------------------------------------------
# 7. ROBUST REGRESSION (TABLE 5)
# ---------------------------------------------------------------------------
def robust_regression(indices):
    """
    Regresses study hours on the three psychosocial indices, WITH and WITHOUT
    the two atypical cases, using the robust Huber estimator.

    WHY ROBUST REGRESSION?
    Two students reported extreme loads (70 and 75 hours) with the lowest
    possible well-being. Classic OLS is very sensitive to such points. The
    Huber M-estimator down-weights them, making it more reliable in the
    presence of outliers.

    OBJECTIVE CRITERION FOR THE OUTLIERS (Tukey's rule for extreme values):
    A value is "extreme" if it exceeds Q3 + 3*IQR. Applied to the hours, this
    threshold (62h) singles out EXACTLY the two cases (70 and 75), with no
    arbitrariness.

    ABOUT R2:
    The Huber estimator does not produce a standard R2. As an AUXILIARY
    indication of fit only, we report the R2 of an OLS on the same predictors.
    That value describes the OLS fit, not the robust model's.
    """
    print("=" * 70)
    print("TABLE 5 - ROBUST (HUBER) REGRESSION OF STUDY HOURS")
    print("=" * 70)
    d = indices.dropna()

    def fit(subset, label):
        X = sm.add_constant(subset[["well_being", "time_management", "online"]])
        y = subset["hours"]
        model = sm.RLM(y, X, M=sm.robust.norms.HuberT()).fit()  # Robust model.
        r2_ols = sm.OLS(y, X).fit().rsquared                    # Auxiliary OLS R2.

        print(f"\n  {label} (n = {len(subset)}):")
        print(f"    {'Predictor':22}{'B':>8}{'SE':>7}{'p':>8}   95% CI")
        names = {"const": "Intercept", "well_being": "Well-being",
                 "time_management": "Time management", "online": "Online strategies"}
        for key in ["const", "well_being", "time_management", "online"]:
            B = model.params[key]
            SE = model.bse[key]
            p = model.pvalues[key]
            lo, hi = model.conf_int().loc[key]
            print(f"    {names[key]:22}{B:8.2f}{SE:7.2f}{p:8.3f}   "
                  f"[{lo:6.2f}, {hi:6.2f}]")
        print(f"    Auxiliary R2 (OLS, same predictors) = {r2_ols:.3f}")

    fit(d, "WITH the two atypical cases")
    fit(d[d.hours < 70], "WITHOUT the two atypical cases (Tukey's rule)")
    print()


# ---------------------------------------------------------------------------
# 8. CLUSTER ANALYSIS (FIGURE 4; ELBOW PLOT AS DIAGNOSTIC ONLY)
# ---------------------------------------------------------------------------
def cluster_analysis(indices):
    """
    Runs k-means on the 67 non-atypical students, validates the two-group
    solution and produces the PCA projection of the groups (Figure 4 in the
    article). An elbow plot is also produced as a diagnostic; it is not shown
    in the article and carries no article figure number.

    WHY SET THE OUTLIERS ASIDE?
    K-means minimises squared distances and is very sensitive to extreme
    values. The two 70-75h cases would form an artificial two-point "group".
    They are described separately and the remaining 67 are clustered.

    VALIDATION OF THE SOLUTION:
      - Silhouette: how well each point fits its group (higher = better).
      - Bootstrap stability (ARI): resample and check whether the groups hold.
      - Agreement with hierarchical clustering (Ward), as a cross-check.
    """
    print("=" * 70)
    print("CLUSTERING (k-means) - FIGURE 4 (elbow plot as diagnostic only)")
    print("=" * 70)
    d = indices.dropna().reset_index(drop=True)
    non_atypical = d[d.hours < 70].reset_index(drop=True)

    variables = ["well_being", "time_management", "online", "hours"]
    X = StandardScaler().fit_transform(non_atypical[variables])

    # --- Main solution: k = 2 on the 67 non-atypical students ---------------
    # n_init=25: k-means is run 25 times with different initial centres and
    # the best solution is kept. With a low n_init (e.g. 10) the algorithm can
    # stop in a local minimum and the indicators change slightly; with 25 or
    # more initialisations the solution here is stable (checked up to
    # n_init=100).
    km = KMeans(n_clusters=2, n_init=25, random_state=RANDOM_STATE).fit(X)
    silhouette = silhouette_score(X, km.labels_)
    ch = calinski_harabasz_score(X, km.labels_)
    ward = AgglomerativeClustering(n_clusters=2, linkage="ward").fit_predict(X)
    ari_ward = adjusted_rand_score(km.labels_, ward)

    # --- Comparison solution: k = 3 on the full sample (n = 69) -------------
    X_full = StandardScaler().fit_transform(d[variables])
    km3 = KMeans(n_clusters=3, n_init=25, random_state=RANDOM_STATE).fit(X_full)
    silhouette_k3 = silhouette_score(X_full, km3.labels_)

    print(f"  Silhouette (k=2, n=67, no outliers) = {silhouette:.4f}")
    print(f"  Silhouette (k=3, n=69, full sample) = {silhouette_k3:.4f}")
    print(f"  Calinski-Harabasz (k=2)             = {ch:.1f}")
    print(f"  K-means vs Ward agreement (ARI)     = {ari_ward:.4f}")

    # --- Stability under bootstrap resampling -------------------------------
    # PROCEDURE (stated explicitly, for full reproducibility):
    #   * 200 resamples WITH replacement, of the same size as the sample;
    #   * indices drawn with numpy.random.default_rng(RANDOM_STATE), so the
    #     sequence of resamples is always the same;
    #   * standardisation (z-scores) is redone WITHIN each resample, because
    #     in practice a researcher would standardise the sample at hand;
    #   * within each resample, a new k-means (n_init=10, random_state=0);
    #   * the resample partition is compared with the original solution
    #     (restricted to the drawn cases; repeated observations remain
    #     repeated, as is proper in the bootstrap) through the ARI, which is
    #     invariant to permutations of the group labels;
    #   * the final indicator is the MEAN of the 200 ARIs.
    def bootstrap_stability(subset, k, original_labels, n_resamples=200):
        rng = np.random.default_rng(RANDOM_STATE)
        aris = []
        for _ in range(n_resamples):
            idx = rng.choice(len(subset), len(subset), replace=True)
            Xb = StandardScaler().fit_transform(subset.iloc[idx][variables])
            labels_b = KMeans(n_clusters=k, n_init=10,
                              random_state=0).fit(Xb).labels_
            aris.append(adjusted_rand_score(original_labels[idx], labels_b))
        return np.mean(aris), np.std(aris)

    ari_boot_k2, sd_k2 = bootstrap_stability(non_atypical, 2, km.labels_)
    ari_boot_k3, sd_k3 = bootstrap_stability(d, 3, km3.labels_)
    print(f"  Bootstrap stability (k=2, n=67)     = mean ARI {ari_boot_k2:.4f}"
          f" (SD {sd_k2:.3f})")
    print(f"  Bootstrap stability (k=3, n=69)     = mean ARI {ari_boot_k3:.4f}"
          f" (SD {sd_k3:.3f})")

    # Characterisation of the two groups (ordered by mean hours).
    non_atypical = non_atypical.copy()
    non_atypical["group"] = km.labels_
    mean_hours = non_atypical.groupby("group").hours.mean().sort_values()
    rename = {mean_hours.index[0]: "Group 1 (low load)",
              mean_hours.index[1]: "Group 2 (high load)"}
    non_atypical["group_name"] = non_atypical.group.map(rename)

    print("\n  TABLE 7 - Characterisation of the groups (means on the original scales):")
    summary = non_atypical.groupby("group_name").agg(
        n=("hours", "size"), hours=("hours", "mean"),
        well_being=("well_being", "mean"),
        time_management=("time_management", "mean"),
        online=("online", "mean"))
    print(summary.round(2).to_string())

    # The two atypical cases are described separately (not clustered).
    atypical = d[d.hours >= 70]
    print("  Atypical cases (n=2):"
          f" hours={atypical.hours.mean():.2f}"
          f" well_being={atypical.well_being.mean():.2f}"
          f" time_management={atypical.time_management.mean():.2f}"
          f" online={atypical.online.mean():.2f}")

    # --- Elbow plot (diagnostic only; not shown in the article) -------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, (subset, title) in zip(
            axes, [(d, "Full sample (n=69)"),
                   (non_atypical, "Without outliers (n=67)")]):
        Xk = StandardScaler().fit_transform(subset[variables])
        inertias = [KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE)
                    .fit(Xk).inertia_ for k in range(1, 7)]
        ax.plot(range(1, 7), inertias, "o-", color="#2E5A87", lw=2, ms=7)
        ax.set_xlabel("Number of groups (k)")
        ax.set_ylabel("Within-group sum of squares")
        ax.set_title(title)
        ax.grid(alpha=0.3)
    plt.tight_layout()
    path_elbow = FIGURES_DIR / "diagnostic_elbow_plot.png"
    plt.savefig(path_elbow, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  [Elbow plot (diagnostic, not in the article) saved to {path_elbow}]")

    # --- Figure 4: PCA projection (computed on all 69) ---------------------
    scaler = StandardScaler().fit(d[variables])
    pca = PCA(n_components=2, random_state=RANDOM_STATE).fit(
        scaler.transform(d[variables]))
    proj = pca.transform(scaler.transform(d[variables]))
    var = pca.explained_variance_ratio_ * 100

    d = d.copy()
    d["p1"], d["p2"] = proj[:, 0], proj[:, 1]
    d["atypical"] = d.hours >= 70
    d["category"] = "-"
    d.loc[~d.atypical, "category"] = non_atypical["group_name"].values
    d.loc[d.atypical, "category"] = "Atypical cases"

    colours = {"Group 1 (low load)": "#FD8D3C",
               "Group 2 (high load)": "#6BAED6",
               "Atypical cases": "#2CA02C"}
    fig, ax = plt.subplots(figsize=(7.5, 5.4))
    for category in colours:
        sub = d[d.category == category]
        ax.scatter(sub.p1, sub.p2, c=colours[category],
                   label=f"{category} (n={len(sub)})", s=55,
                   edgecolor="white", linewidth=0.5,
                   marker="D" if category == "Atypical cases" else "o",
                   zorder=6 if category == "Atypical cases" else 3)
    ax.set_xlabel(f"PCA 1 ({var[0]:.1f}% of variance)")
    ax.set_ylabel(f"PCA 2 ({var[1]:.1f}% of variance)")
    ax.legend(title="Clustering", frameon=True, loc="lower right",
              fontsize=9, framealpha=0.9)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    path_pca = FIGURES_DIR / "figure4_pca_projection.png"
    plt.savefig(path_pca, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 4 saved to {path_pca}]\n")


# ---------------------------------------------------------------------------
# 9. DESCRIPTIVE FIGURES (FIGURE 2; BY-GENDER BOX PLOTS AS DIAGNOSTIC ONLY)
# ---------------------------------------------------------------------------
def figure2_boxplots(indices):
    """
    Figure 2 of the article: box plots of the three normalised indices.

    Reflects the final operationalisation: well-being with 6 items, time
    management with 3 items (the index can only take the values 0, 1/3, 2/3
    and 1, hence the "stepped" box) and online strategies with 5 digital
    options.
    """
    d = indices.dropna()
    series = [d["well_being"], d["time_management"], d["online"]]
    labels = ["Well-being", "Time management", "Online academic strategies"]
    colours = ["#9FB2D8", "#FA8B6B", "#66C2A5"]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    boxes = ax.boxplot(series, labels=labels, patch_artist=True,
                       medianprops=dict(color="black", lw=2))
    for box, colour in zip(boxes["boxes"], colours):
        box.set_facecolor(colour)
    ax.set_ylabel("Normalised score (0-1)")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path = FIGURES_DIR / "figure2_index_boxplots.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure 2 saved to {path}]\n")


def diagnostic_gender_boxplots(data, indices):
    """
    Diagnostic figure (not shown in the article): distribution of the three
    indices by gender, with the Mann-Whitney p-value and Cliff's delta in the
    title of each panel.

    The by-gender box plots were dropped from the article because the gender
    contrast is fully reported by the statistics and effect sizes in Table 6;
    the plot is kept here as a diagnostic and carries no article figure number.
    The values are COMPUTED here (not copied), so the figure stays consistent
    with Table 6.
    """
    d = indices.copy()
    d["gender"] = data[7]
    d = d.dropna(subset=["hours", "well_being", "time_management", "online"])
    male, female = d[d.gender == "Masculino"], d[d.gender == "Feminino"]

    panels = [("online", "Academic strategies by gender"),
              ("time_management", "Time management by gender"),
              ("well_being", "Well-being by gender")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, (column, title) in zip(axes, panels):
        _, p = stats.mannwhitneyu(male[column], female[column],
                                  alternative="two-sided")
        delta = cliff_delta(male[column], female[column])
        magnitude = ("medium" if abs(delta) >= .33 else
                     ("small" if abs(delta) >= .147 else "negligible"))
        boxes = ax.boxplot([male[column], female[column]],
                           labels=[f"Male\n(n={len(male)})",
                                   f"Female\n(n={len(female)})"],
                           patch_artist=True,
                           medianprops=dict(color="black", lw=2))
        for box, colour in zip(boxes["boxes"], ["#6A8FC7", "#E8A075"]):
            box.set_facecolor(colour)
        ax.set_title(f"{title}\nMann-Whitney U: p = {p:.3f} - "
                     f"Cliff's d = {delta:.2f} ({magnitude})", fontsize=10)
        ax.set_ylabel("Normalised score (0-1)")
        ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path = FIGURES_DIR / "diagnostic_gender_boxplots.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [By-gender box plots (diagnostic, not in the article) saved to {path}]\n")


# ---------------------------------------------------------------------------
# 10. TEXT ANALYSIS OF THE OPEN-ENDED RESPONSES (SECTION 3.9 OF THE ARTICLE)
# ---------------------------------------------------------------------------
# The open-ended responses are analysed by A PRIORI THEMATIC CATEGORY, that
# is, by the five blocks of the questionnaire itself. This choice replaces the
# exploratory lexical clustering of earlier versions: because the categories
# come from the design of the instrument, there is no number of groups to
# choose or to justify.
#
# The corpus uses ONLY the FREE-TEXT items. Two closed-format items that
# belong to the same thematic blocks are left out: the multiple-choice
# question about challenges (column 38, whose pre-defined options -- "manter a
# concentracao" / keeping concentration, "procrastinacao" / procrastination,
# "sobrecarga de tarefas" / task overload -- would inflate the frequencies
# with text that does not come from the students) and the yes/no question
# about asking for help (column 51, with no lexical content).

# Map: thematic category -> free-text columns in the questionnaire.
TEXT_CATEGORIES = {
    "Motivations and views":            [58, 59],
    "Self-assessment and strategies":   [35, 37, 55],
    "Challenges and resources":         [48, 49],
    "Interaction and support":          [52],
    "Reflection and final comments":    [65, 66, 67],
}

# Portuguese function words (stop-words), plus a small set of English function
# words (some students answered in English). The list lives in the program
# itself so that it does not depend on external packages.
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


def _tokenize(text):
    """
    Splits a response into words (tokens) for the lexical analysis.

    Steps: lower-case; remove punctuation; split on whitespace; discard words
    shorter than 3 letters, numbers and stop-words. The comparison against
    the stop-word list is done WITHOUT accents ("tambem" with and without the
    accent are the same word), but the token keeps its original spelling, so
    that reading stays natural. As in the previous version of the article, no
    stemming or lemmatisation is applied.
    """
    text = str(text).lower()
    text = re.sub(r"[^\w\s\u00e1\u00e0\u00e2\u00e3\u00e9\u00ea\u00ed\u00f3\u00f4\u00f5\u00fa\u00fc\u00e7-]", " ", text)
    tokens = []
    for word in text.split():
        word = word.strip("-")
        if (len(word) >= 3 and not word.isdigit()
                and strip_accents(word) not in STOPWORDS_PT):
            tokens.append(word)
    return tokens


def _g2_log_likelihood(freq_in, freq_out, total_in, total_out):
    """
    G2 log-likelihood ratio (Dunning, 1993) for "keyness": measures whether a
    term is more frequent in a category than in the rest of the corpus, beyond
    what chance would explain. The larger the G2, the more characteristic the
    term. It is used here as a DESCRIPTIVE RANKING, not as a formal test (no
    p-values, no correction for multiple comparisons), as stated in the
    article.
    """
    total = total_in + total_out
    expected_in = total_in * (freq_in + freq_out) / total
    expected_out = total_out * (freq_in + freq_out) / total
    g2 = 0.0
    if freq_in > 0:
        g2 += freq_in * np.log(freq_in / expected_in)
    if freq_out > 0:
        g2 += freq_out * np.log(freq_out / expected_out)
    return 2 * g2


def text_analysis(header, data):
    """
    Reproduces Section 3.9 of the article: lexical analysis of the open-ended
    responses by a priori thematic category.

      1. Builds the corpus from the 11 free-text items (one "response" = one
         student's text on one item), ignoring empty or contentless answers
         ("sim", "nao", "-").
      2. Counts the global term frequencies and, if the `wordcloud` package is
         installed, generates a word cloud. The word cloud was dropped from the
         article (raw frequencies say little about what is distinctive of each
         category); it is kept here as a diagnostic and carries no article
         figure number.
      3. For each category, identifies the most characteristic terms (highest
         G2 against the rest of the corpus), requiring a minimum frequency of
         4 occurrences within the category (Table 9).
    """
    from collections import Counter

    print("=" * 70)
    print("SECTION 3.9 - TEXT ANALYSIS BY THEMATIC CATEGORY")
    print("=" * 70)

    # --- 1. Corpus ----------------------------------------------------------
    responses = []   # list of (category, text) tuples
    for category, columns in TEXT_CATEGORIES.items():
        for column in columns:
            for value in data[column].dropna():
                text = str(value).strip()
                if text and strip_accents(text.lower()) not in (
                        "sim", "nao", "-", "n/a", "na"):
                    responses.append((category, text))
    corpus = pd.DataFrame(responses, columns=["category", "text"])
    corpus["tokens"] = corpus["text"].apply(_tokenize)
    print(f"  Corpus: {len(corpus)} non-empty responses, "
          f"{len(TEXT_CATEGORIES)} categories.")
    print(corpus["category"].value_counts().to_string())

    # --- 2. Global frequencies and word cloud (diagnostic; not in article) --
    frequencies = Counter(t for tokens in corpus["tokens"] for t in tokens)
    print("\n  Most frequent terms in the corpus (top 15):")
    for term, freq in frequencies.most_common(15):
        print(f"    {term:20} {freq}")

    try:
        from wordcloud import WordCloud
        cloud = WordCloud(width=1400, height=800, background_color="white",
                          colormap="viridis", random_state=RANDOM_STATE,
                          max_words=100).generate_from_frequencies(frequencies)
        fig, ax = plt.subplots(figsize=(11, 6.5))
        ax.imshow(cloud, interpolation="bilinear")
        ax.axis("off")
        plt.tight_layout()
        path = FIGURES_DIR / "diagnostic_wordcloud.png"
        plt.savefig(path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\n  [Word cloud (diagnostic, not in the article) saved to {path}]")
    except ImportError:
        print("\n  [The 'wordcloud' package is not installed; the diagnostic word "
              "cloud was not generated. Install it with: pip install wordcloud]")

    # --- 3. Characteristic terms per category (Table 9) --------------------
    print("\n  TABLE 9 - Most characteristic terms of each category")
    print("  (G2 log-likelihood ratio vs. the rest of the corpus; min. frequency 4)")
    table_rows = []
    for category in TEXT_CATEGORIES:
        inside = Counter(t for tokens in
                         corpus.loc[corpus.category == category, "tokens"]
                         for t in tokens)
        outside = Counter(t for tokens in
                          corpus.loc[corpus.category != category, "tokens"]
                          for t in tokens)
        total_in, total_out = sum(inside.values()), sum(outside.values())

        candidates = []
        for term, freq in inside.items():
            if freq < 4:
                continue  # rare terms are not informative
            # Only OVER-represented terms in the category are of interest.
            if freq / total_in <= outside.get(term, 0) / total_out:
                continue
            g2 = _g2_log_likelihood(freq, outside.get(term, 0),
                                    total_in, total_out)
            candidates.append((term, freq, g2))
        candidates.sort(key=lambda x: -x[2])

        top5 = candidates[:5]
        terms_str = ", ".join(f"{t} (f={f}, G2={g:.1f})" for t, f, g in top5)
        print(f"    {category}:")
        print(f"      {terms_str}")
        for t, f, g in top5:
            table_rows.append({"category": category, "term": t,
                               "frequency": f, "G2": round(g, 1)})

    table9 = pd.DataFrame(table_rows)
    csv_path = FIGURES_DIR / "table9_terms_by_category.csv"
    table9.to_csv(csv_path, index=False)
    print(f"\n  [Table 9 saved to {csv_path}]\n")


# ---------------------------------------------------------------------------
# 11. MAIN FUNCTION - orchestrates the whole analysis in the article's order
# ---------------------------------------------------------------------------
def main():
    """Runs the complete analysis, from data loading to the figures."""
    header, data = load_data()
    indices, digital_core = build_indices(data)

    compute_reliabilities(data, digital_core)
    descriptive_table(indices)          # Table 4
    figure2_boxplots(indices)           # Figure 2
    spearman_correlations(indices)      # Figure 3
    robust_regression(indices)          # Table 5
    gender_differences(data, indices)   # Table 6
    cluster_analysis(indices)           # Figure 4 + Table 7 (elbow = diagnostic)
    text_analysis(header, data)         # Table 9 (word cloud = diagnostic)

    # Diagnostic figure kept for completeness; not shown in the article.
    diagnostic_gender_boxplots(data, indices)

    print("=" * 70)
    print("ANALYSIS COMPLETE. Article figures and the diagnostic plots are in")
    print("the ./figures/ folder.")
    print("=" * 70)


# main() only runs when the file is executed directly (not when imported).
if __name__ == "__main__":
    main()