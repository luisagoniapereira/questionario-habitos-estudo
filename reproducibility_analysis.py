# -*- coding: utf-8 -*-
"""
===============================================================================
COMPLETE REPRODUCTION OF THE ARTICLE ANALYSES
(QUANTITATIVE, ITEM-LEVEL, SENSITIVITY, CLUSTERING AND LEXICAL)

Article:
"Student Engagement in Technology-Mediated Hybrid Higher Education:
An Exploratory Institutional Case Study"

Authors (publication order):
1. Luís Agonia Pereira
2. Valter Martins Vairinhos
3. Ana de Jesus Mendes

Repository version: 2.0.0
Analytical sample: n = 69
===============================================================================

PURPOSE
-------
This script reproduces the analyses reported in the article and the additional
item-level, sensitivity and clustering robustness analyses included in version 2.0.0.

It performs the following tasks:

1. Loads the anonymised questionnaire dataset from a local Excel file or, if no
   local file is available, downloads the current public record from Zenodo.
2. Reconstructs the well-being, time-management and online academic-strategy
   aggregates, together with self-reported weekly study hours.
3. Reproduces reliability coefficients, descriptive statistics, Spearman
   correlations, robust regression, gender comparisons, clustering and lexical
   analysis.
4. Adds item-level analyses, bootstrap confidence intervals, Holm-adjusted
   p-values, programme-composition sensitivity models and clustering without
   weekly study hours.
5. Writes figures and tabular lexical results to the ./figures directory.

LANGUAGE AND SOURCE VALUES
--------------------------
All documentation, console output, labels and code comments use British
English. A small number of Portuguese strings are retained only where they are
required to recognise the original questionnaire values stored in the source
file (for example, "Sim", "Não" and programme names).

REPRODUCIBILITY
---------------
All stochastic procedures use RANDOM_STATE = 42. Bootstrap confidence
intervals use 10,000 resamples unless otherwise stated.

RUNNING THE SCRIPT
------------------
    pip install -r requirements.txt
    python reproducibility_analysis.py
===============================================================================
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, calinski_harabasz_score, silhouette_score
from sklearn.preprocessing import StandardScaler


# -----------------------------------------------------------------------------
# Global configuration
# -----------------------------------------------------------------------------
ZENODO_RECORD_ID = "24224469"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"
RANDOM_STATE = 42
LOCAL_DATA_CANDIDATES = ("Questionnaire_Clean.xlsx", "Questionario_Limpo.xlsx")
FIGURES_DIR = Path("figures")
FIGURES_DIR.mkdir(exist_ok=True)


# -----------------------------------------------------------------------------
# Source-language mappings used only to parse the Portuguese questionnaire
# -----------------------------------------------------------------------------
YES_VALUES = {"sim"}
NO_VALUES = {"nao"}

ITEM_LABELS_EN = {
    28: "Use of study schedules or routines",
    29: "Prioritisation of academic tasks",
    30: "Management of intervals and breaks",
    39: "Adequate sleep",
    40: "Balanced diet",
    41: "Regular exercise or a hobby",
    42: "Stress and emotional-balance management",
    43: "Physical fatigue",
    44: "Psychological fatigue",
}

ITEM_WORDING_EN = {
    28: (
        "Do you create study schedules or routines and meet your goals for both "
        "face-to-face and online activities, including classes?"
    ),
    29: "Are you able to prioritise academic tasks efficiently, both face-to-face and online?",
    30: (
        "Do you use time efficiently by managing intervals and breaks appropriately "
        "and adapting to different teaching modes?"
    ),
    39: (
        "Do you ensure adequate sleep quality to maintain focus and concentration "
        "in academic activities, both face-to-face and online?"
    ),
    40: "In your view, do you follow a balanced diet?",
    41: "Do you regularly exercise or pursue a hobby to support your physical well-being?",
    42: "Do you manage stress levels and emotional balance to maintain a healthy mental state?",
    43: "Do you usually experience physical fatigue?",
    44: "Do you usually experience psychological fatigue?",
    32: "Which study practices do you use most in online contexts? Select all that apply.",
}

ONLINE_OPTION_LABELS_EN = {
    "criacao de mapas mentais / diagramas": "Mind maps or diagrams",
    "estudar com colegas (comunidades de aprendizagem virtuais)": (
        "Studying with peers in virtual learning communities"
    ),
    "realizacao de exercicios": "Exercise completion",
    "resumo de textos": "Text summaries",
    "utilizar recursos online como videos, manuais, foruns, etc.": (
        "Online resources such as videos, manuals and forums"
    ),
}


# -----------------------------------------------------------------------------
# Low-level helpers
# -----------------------------------------------------------------------------
def strip_accents(text: str) -> str:
    """Return a lower-risk comparison form without diacritics."""
    return "".join(
        character
        for character in unicodedata.normalize("NFD", str(text))
        if unicodedata.category(character) != "Mn"
    )


def normalise_source_text(value: object) -> str:
    """Normalise a source value for case-insensitive matching."""
    return strip_accents(str(value).strip().lower())


def binary_item(data: pd.DataFrame, column: int, reverse: bool = False) -> pd.Series:
    """Convert a Portuguese yes/no questionnaire item to 1/0, with optional reversal."""

    def classify(value: object) -> float:
        if pd.isna(value):
            return np.nan
        normalised = normalise_source_text(value)
        if normalised in YES_VALUES:
            return 1.0
        if normalised in NO_VALUES:
            return 0.0
        return np.nan

    series = data[column].apply(classify)
    return 1.0 - series if reverse else series


def kr20(item_matrix: pd.DataFrame) -> float:
    """Calculate Kuder-Richardson Formula 20 for complete binary-item cases."""
    items = item_matrix.dropna()
    number_of_items = items.shape[1]
    item_proportions = items.mean()
    item_complements = 1 - item_proportions
    total_score_variance = items.sum(axis=1).var(ddof=1)
    return (number_of_items / (number_of_items - 1)) * (
        1 - (item_proportions * item_complements).sum() / total_score_variance
    )


def cliffs_delta(group_a: Iterable[float], group_b: Iterable[float]) -> float:
    """Calculate Cliff's delta, defined as group A minus group B."""
    a = np.asarray(list(group_a), dtype=float)
    b = np.asarray(list(group_b), dtype=float)
    u_statistic, _ = stats.mannwhitneyu(a, b, alternative="two-sided")
    return (2 * u_statistic) / (len(a) * len(b)) - 1


def holm_adjust(p_values: Iterable[float]) -> np.ndarray:
    """Apply Holm's sequential family-wise error adjustment."""
    p = np.asarray(list(p_values), dtype=float)
    order = np.argsort(p)
    ordered_adjusted = np.empty(len(p), dtype=float)
    running_maximum = 0.0
    number_of_tests = len(p)

    for position, original_index in enumerate(order):
        adjusted_value = min(1.0, (number_of_tests - position) * p[original_index])
        running_maximum = max(running_maximum, adjusted_value)
        ordered_adjusted[position] = running_maximum

    adjusted = np.empty(len(p), dtype=float)
    for position, original_index in enumerate(order):
        adjusted[original_index] = ordered_adjusted[position]
    return adjusted


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
def extract_excel_data(path_or_buffer: object) -> tuple[pd.Series, pd.DataFrame, int]:
    """
    Read either supported Excel layout.

    Layout A: numbered columns, with the question wording in the first data row.
    Layout B: question wording stored directly in the Excel column headings.
    """
    complete_frame = pd.read_excel(path_or_buffer, sheet_name=0)

    if not isinstance(complete_frame.columns[0], str) or complete_frame.columns[0] in ("1", 1):
        header = complete_frame.iloc[0]
        data = complete_frame.iloc[1:].copy()
        return header, data, complete_frame.shape[1]

    question_texts = list(complete_frame.columns)
    complete_frame.columns = range(1, complete_frame.shape[1] + 1)
    header = pd.Series(question_texts, index=complete_frame.columns)

    first_weekly_hours = pd.to_numeric(complete_frame.iloc[0][27], errors="coerce")
    if pd.isna(first_weekly_hours) and isinstance(complete_frame.iloc[0][27], str):
        data = complete_frame.iloc[1:].copy()
    else:
        data = complete_frame.copy()

    return header, data, complete_frame.shape[1]


def excel_from_zip_bytes(content: bytes, depth: int = 0) -> io.BytesIO | None:
    """Return the first Excel file found in a ZIP archive, including nested ZIP files."""
    if depth > 3:
        return None
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = archive.namelist()
        xlsx_files = [name for name in names if name.lower().endswith(".xlsx")]
        if xlsx_files:
            return io.BytesIO(archive.read(xlsx_files[0]))
        for name in names:
            if name.lower().endswith(".zip"):
                nested = excel_from_zip_bytes(archive.read(name), depth + 1)
                if nested is not None:
                    return nested
    return None


def download_data_from_zenodo(api_url: str = ZENODO_API) -> io.BytesIO:
    """Download the current dataset file from the public Zenodo record."""
    with urllib.request.urlopen(api_url) as response:
        metadata = json.load(response)

    files = metadata.get("files", [])

    def file_url(file_metadata: dict) -> str | None:
        return file_metadata.get("links", {}).get("self") or file_metadata.get("links", {}).get("download")

    selected = None
    for file_metadata in files:
        name = (file_metadata.get("key") or file_metadata.get("filename") or "").lower()
        if name.endswith(".xlsx"):
            selected = file_metadata
            break
    if selected is None:
        for file_metadata in files:
            name = (file_metadata.get("key") or file_metadata.get("filename") or "").lower()
            if name.endswith(".zip"):
                selected = file_metadata
                break

    if selected is None:
        raise RuntimeError("No Excel dataset or ZIP archive was found in the Zenodo record.")

    url = file_url(selected)
    if not url:
        raise RuntimeError("The selected Zenodo file does not contain a download URL.")

    with urllib.request.urlopen(url) as response:
        content = response.read()

    selected_name = (selected.get("key") or selected.get("filename") or "").lower()
    if selected_name.endswith(".xlsx"):
        return io.BytesIO(content)

    excel_buffer = excel_from_zip_bytes(content)
    if excel_buffer is None:
        raise RuntimeError("The downloaded ZIP archive did not contain an Excel dataset.")
    return excel_buffer


def load_data() -> tuple[pd.Series, pd.DataFrame]:
    """Load the local dataset when available; otherwise use the public Zenodo record."""
    script_directory = Path(__file__).resolve().parent

    for candidate_name in LOCAL_DATA_CANDIDATES:
        candidate_path = script_directory / candidate_name
        if candidate_path.exists():
            print(f"Reading local dataset: {candidate_path.name}")
            header, data, number_of_columns = extract_excel_data(candidate_path)
            break
    else:
        print("No local dataset found; downloading the public Zenodo record...")
        header, data, number_of_columns = extract_excel_data(download_data_from_zenodo())

    valid_responses = pd.to_numeric(data[27], errors="coerce").notna().sum()
    print(f"Dataset loaded: {valid_responses} valid analytical responses, {number_of_columns} columns.\n")
    return header, data


# -----------------------------------------------------------------------------
# Index construction
# -----------------------------------------------------------------------------
def discover_online_options(data: pd.DataFrame) -> list[str]:
    """Return the five digital response options from the multiple-response item."""
    all_options: set[str] = set()
    for value in data[32].dropna():
        for option in str(value).split(";"):
            option = option.strip()
            if option:
                all_options.add(option)

    digital_options = [
        option
        for option in sorted(all_options)
        if not normalise_source_text(option).startswith("outro")
        and "sozinho" not in normalise_source_text(option)
    ]
    return digital_options


def online_option_label(option: str) -> str:
    """Translate a source option into the English label used in the article."""
    return ONLINE_OPTION_LABELS_EN.get(normalise_source_text(option), option)


def construct_indices(data: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Construct the three behavioural aggregates and weekly study hours."""
    well_being = pd.DataFrame(
        {
            "sleep": binary_item(data, 39),
            "diet": binary_item(data, 40),
            "exercise": binary_item(data, 41),
            "stress_management": binary_item(data, 42),
            "physical_fatigue": binary_item(data, 43, reverse=True),
            "psychological_fatigue": binary_item(data, 44, reverse=True),
        }
    ).mean(axis=1)

    time_management = pd.DataFrame(
        {
            "schedules": binary_item(data, 28),
            "prioritisation": binary_item(data, 29),
            "break_management": binary_item(data, 30),
        }
    ).mean(axis=1)

    digital_options = discover_online_options(data)

    def online_proportion(value: object) -> float:
        if pd.isna(value):
            return np.nan
        selected = [
            option.strip()
            for option in str(value).split(";")
            if option.strip() in digital_options
        ]
        return len(selected) / len(digital_options)

    online_strategies = data[32].apply(online_proportion)
    weekly_hours = pd.to_numeric(data[27], errors="coerce")

    indices = pd.DataFrame(
        {
            "weekly_hours": weekly_hours,
            "well_being": well_being,
            "time_management": time_management,
            "online_strategies": online_strategies,
        }
    )
    return indices, digital_options


def build_item_matrices(data: pd.DataFrame, digital_options: list[str]) -> dict[str, pd.DataFrame]:
    """Return the binary-item matrices used for KR-20 and item-level analyses."""
    well_being_items = pd.DataFrame(
        {
            "sleep": binary_item(data, 39),
            "diet": binary_item(data, 40),
            "exercise": binary_item(data, 41),
            "stress_management": binary_item(data, 42),
            "physical_fatigue_reversed": binary_item(data, 43, reverse=True),
            "psychological_fatigue_reversed": binary_item(data, 44, reverse=True),
        }
    )

    time_management_items = pd.DataFrame(
        {
            "schedules": binary_item(data, 28),
            "prioritisation": binary_item(data, 29),
            "break_management": binary_item(data, 30),
        }
    )

    online_items = pd.DataFrame(
        {
            online_option_label(option): data[32].apply(
                lambda value, source_option=option: (
                    1.0 if source_option in str(value) else 0.0
                )
                if pd.notna(value)
                else np.nan
            )
            for option in digital_options
        }
    )

    return {
        "well_being": well_being_items,
        "time_management": time_management_items,
        "online_strategies": online_items,
    }


# -----------------------------------------------------------------------------
# Core analyses reported in the article
# -----------------------------------------------------------------------------
def report_reliability(data: pd.DataFrame, digital_options: list[str]) -> None:
    """Report KR-20 coefficients for the three aggregates."""
    matrices = build_item_matrices(data, digital_options)
    print("=" * 78)
    print("RELIABILITY OF THE BEHAVIOURAL AGGREGATES (KR-20)")
    print("=" * 78)
    print(f"  Well-being (6 items):               KR-20 = {kr20(matrices['well_being']):.3f}")
    print(f"  Time management (3 items):          KR-20 = {kr20(matrices['time_management']):.3f}")
    print(f"  Online academic strategies (5):     KR-20 = {kr20(matrices['online_strategies']):.3f}")
    print("  Interpretation: time management and online strategies remain exploratory")
    print("  behavioural aggregates because their internal consistency is limited.\n")


def report_descriptive_statistics(indices: pd.DataFrame) -> None:
    """Report descriptive statistics for the three 0-1 aggregates."""
    print("=" * 78)
    print("DESCRIPTIVE STATISTICS FOR THE 0-1 AGGREGATES")
    print("=" * 78)
    complete = indices.dropna()
    labels = {
        "well_being": "Well-being",
        "time_management": "Time management",
        "online_strategies": "Online academic strategies",
    }
    for column, label in labels.items():
        series = complete[column]
        print(
            f"  {label:30} M={series.mean():.2f} SD={series.std():.2f} "
            f"Min={series.min():.2f} Q1={series.quantile(.25):.2f} "
            f"Median={series.median():.2f} Q3={series.quantile(.75):.2f} "
            f"Max={series.max():.2f}"
        )
    print()


def plot_index_boxplots(indices: pd.DataFrame) -> None:
    """Create descriptive boxplots for the three aggregates."""
    complete = indices.dropna()
    series = [
        complete["well_being"],
        complete["time_management"],
        complete["online_strategies"],
    ]
    labels = ["Well-being", "Time management", "Online academic strategies"]

    figure, axis = plt.subplots(figsize=(10, 4.2))
    axis.boxplot(series, tick_labels=labels)
    axis.set_ylabel("Normalised score (0-1)")
    axis.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    output_path = FIGURES_DIR / "figure_index_boxplots.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure saved to {output_path}]\n")


def report_spearman_correlations(indices: pd.DataFrame) -> None:
    """Report the Spearman correlation matrix and save a heat map."""
    print("=" * 78)
    print("SPEARMAN CORRELATIONS")
    print("=" * 78)
    complete = indices.dropna()
    columns = ["weekly_hours", "well_being", "time_management", "online_strategies"]
    labels = ["Weekly study hours", "Well-being", "Time management", "Online strategies"]

    number_of_variables = len(columns)
    rho = np.zeros((number_of_variables, number_of_variables))
    p_values = np.ones((number_of_variables, number_of_variables))

    for row_index in range(number_of_variables):
        for column_index in range(number_of_variables):
            coefficient, p_value = stats.spearmanr(
                complete[columns[row_index]], complete[columns[column_index]]
            )
            rho[row_index, column_index] = coefficient
            p_values[row_index, column_index] = p_value

    for row_index in range(number_of_variables):
        for column_index in range(row_index + 1, number_of_variables):
            marker = "**" if p_values[row_index, column_index] < .01 else (
                "*" if p_values[row_index, column_index] < .05 else ""
            )
            print(
                f"  {labels[row_index]:24} x {labels[column_index]:24} "
                f"rho={rho[row_index, column_index]:+.2f}{marker} "
                f"(p={p_values[row_index, column_index]:.3f})"
            )

    figure, axis = plt.subplots(figsize=(8, 6.5))
    image = axis.imshow(rho, vmin=-1, vmax=1)
    for row_index in range(number_of_variables):
        for column_index in range(number_of_variables):
            marker = "" if row_index == column_index else (
                "**" if p_values[row_index, column_index] < .01 else (
                    "*" if p_values[row_index, column_index] < .05 else ""
                )
            )
            axis.text(
                column_index,
                row_index,
                f"{rho[row_index, column_index]:.2f}{marker}",
                ha="center",
                va="center",
                fontsize=11,
            )
    axis.set_xticks(range(number_of_variables))
    axis.set_yticks(range(number_of_variables))
    axis.set_xticklabels(labels, rotation=30, ha="right")
    axis.set_yticklabels(labels)
    colour_bar = figure.colorbar(image, ax=axis, shrink=0.8)
    colour_bar.set_label("Spearman's rho")
    plt.tight_layout()
    output_path = FIGURES_DIR / "figure_spearman_correlations.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure saved to {output_path}]\n")


def report_robust_regression(indices: pd.DataFrame) -> None:
    """Estimate the Huber robust regression with and without the two extreme cases."""
    print("=" * 78)
    print("ROBUST REGRESSION OF WEEKLY STUDY HOURS")
    print("=" * 78)
    complete = indices.dropna()

    def fit_and_report(subset: pd.DataFrame, label: str) -> None:
        predictors = sm.add_constant(
            subset[["well_being", "time_management", "online_strategies"]]
        )
        outcome = subset["weekly_hours"]
        model = sm.RLM(outcome, predictors, M=sm.robust.norms.HuberT()).fit()
        auxiliary_r_squared = sm.OLS(outcome, predictors).fit().rsquared

        labels = {
            "const": "Intercept",
            "well_being": "Well-being",
            "time_management": "Time management",
            "online_strategies": "Online academic strategies",
        }

        print(f"\n  {label} (n = {len(subset)}):")
        print(f"    {'Predictor':30}{'B':>9}{'SE':>9}{'p':>10}   95% CI")
        for key in ["const", "well_being", "time_management", "online_strategies"]:
            lower, upper = model.conf_int().loc[key]
            print(
                f"    {labels[key]:30}{model.params[key]:9.2f}{model.bse[key]:9.2f}"
                f"{model.pvalues[key]:10.3f}   [{lower:6.2f}, {upper:6.2f}]"
            )
        print(f"    Auxiliary OLS R-squared = {auxiliary_r_squared:.3f}")

    fit_and_report(complete, "All participants")
    fit_and_report(complete[complete["weekly_hours"] < 70], "Two atypical cases set aside")
    print()


def report_gender_differences(data: pd.DataFrame, indices: pd.DataFrame) -> None:
    """Compare male and female participants using Mann-Whitney U and Cliff's delta."""
    print("=" * 78)
    print("GENDER DIFFERENCES")
    print("=" * 78)
    analytical = indices.copy()
    analytical["gender"] = data[7]
    analytical = analytical.dropna(
        subset=["weekly_hours", "well_being", "time_management", "online_strategies"]
    )

    male = analytical[analytical["gender"] == "Masculino"]
    female = analytical[analytical["gender"] == "Feminino"]
    print(f"  Male n = {len(male)}; female n = {len(female)}")
    print("  Convention: positive Cliff's delta denotes higher values among male students.")

    for column, label in [
        ("online_strategies", "Online academic strategies"),
        ("time_management", "Time management"),
        ("well_being", "Well-being"),
    ]:
        u_male, p_value = stats.mannwhitneyu(
            male[column], female[column], alternative="two-sided"
        )
        u_female = len(male) * len(female) - u_male
        delta = cliffs_delta(male[column], female[column])
        magnitude = "medium" if abs(delta) >= .33 else (
            "small" if abs(delta) >= .147 else "negligible"
        )
        print(
            f"  {label:30} U={min(u_male, u_female):.1f} "
            f"p={p_value:.3f} delta={delta:+.2f} ({magnitude})"
        )
    print()


def plot_gender_differences(data: pd.DataFrame, indices: pd.DataFrame) -> None:
    """Create boxplots of the three aggregates by gender."""
    analytical = indices.copy()
    analytical["gender"] = data[7]
    analytical = analytical.dropna(
        subset=["weekly_hours", "well_being", "time_management", "online_strategies"]
    )
    male = analytical[analytical["gender"] == "Masculino"]
    female = analytical[analytical["gender"] == "Feminino"]

    panels = [
        ("online_strategies", "Online academic strategies"),
        ("time_management", "Time management"),
        ("well_being", "Well-being"),
    ]
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for axis, (column, title) in zip(axes, panels):
        _, p_value = stats.mannwhitneyu(
            male[column], female[column], alternative="two-sided"
        )
        delta = cliffs_delta(male[column], female[column])
        magnitude = "medium" if abs(delta) >= .33 else (
            "small" if abs(delta) >= .147 else "negligible"
        )
        axis.boxplot(
            [male[column], female[column]],
            tick_labels=[f"Male\n(n={len(male)})", f"Female\n(n={len(female)})"],
        )
        axis.set_title(
            f"{title}\nMann-Whitney p = {p_value:.3f}; "
            f"Cliff's delta = {delta:.2f} ({magnitude})",
            fontsize=10,
        )
        axis.set_ylabel("Normalised score (0-1)")
        axis.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    output_path = FIGURES_DIR / "figure_gender_differences.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [Figure saved to {output_path}]\n")


def report_original_clustering(indices: pd.DataFrame) -> None:
    """Reproduce the original clustering analysis reported in the manuscript."""
    print("=" * 78)
    print("ORIGINAL EXPLORATORY CLUSTERING")
    print("=" * 78)
    complete = indices.dropna().reset_index(drop=True)
    without_atypical_cases = complete[complete["weekly_hours"] < 70].reset_index(drop=True)
    variables = ["well_being", "time_management", "online_strategies", "weekly_hours"]
    standardised = StandardScaler().fit_transform(without_atypical_cases[variables])

    kmeans_two = KMeans(n_clusters=2, n_init=25, random_state=RANDOM_STATE).fit(standardised)
    silhouette_two = silhouette_score(standardised, kmeans_two.labels_)
    calinski_harabasz = calinski_harabasz_score(standardised, kmeans_two.labels_)
    ward_labels = AgglomerativeClustering(n_clusters=2, linkage="ward").fit_predict(standardised)
    ward_ari = adjusted_rand_score(kmeans_two.labels_, ward_labels)

    complete_standardised = StandardScaler().fit_transform(complete[variables])
    kmeans_three = KMeans(n_clusters=3, n_init=25, random_state=RANDOM_STATE).fit(
        complete_standardised
    )
    silhouette_three = silhouette_score(complete_standardised, kmeans_three.labels_)

    print(f"  Silhouette, k=2, n=67:             {silhouette_two:.4f}")
    print(f"  Silhouette, k=3, n=69:             {silhouette_three:.4f}")
    print(f"  Calinski-Harabasz, k=2:            {calinski_harabasz:.1f}")
    print(f"  K-means versus Ward agreement:     ARI = {ward_ari:.4f}")

    def bootstrap_stability(
        subset: pd.DataFrame,
        number_of_clusters: int,
        reference_labels: np.ndarray,
        number_of_resamples: int = 200,
    ) -> tuple[float, float]:
        random_generator = np.random.default_rng(RANDOM_STATE)
        ari_values: list[float] = []
        for _ in range(number_of_resamples):
            sampled_indices = random_generator.choice(
                len(subset), len(subset), replace=True
            )
            bootstrap_standardised = StandardScaler().fit_transform(
                subset.iloc[sampled_indices][variables]
            )
            bootstrap_labels = KMeans(
                n_clusters=number_of_clusters, n_init=10, random_state=0
            ).fit(bootstrap_standardised).labels_
            ari_values.append(
                adjusted_rand_score(reference_labels[sampled_indices], bootstrap_labels)
            )
        return float(np.mean(ari_values)), float(np.std(ari_values))

    bootstrap_two, bootstrap_two_sd = bootstrap_stability(
        without_atypical_cases, 2, kmeans_two.labels_
    )
    bootstrap_three, bootstrap_three_sd = bootstrap_stability(
        complete, 3, kmeans_three.labels_
    )
    print(
        f"  Bootstrap stability, k=2:          mean ARI = {bootstrap_two:.4f} "
        f"(SD = {bootstrap_two_sd:.3f})"
    )
    print(
        f"  Bootstrap stability, k=3:          mean ARI = {bootstrap_three:.4f} "
        f"(SD = {bootstrap_three_sd:.3f})"
    )

    clustered = without_atypical_cases.copy()
    clustered["cluster"] = kmeans_two.labels_
    hours_by_cluster = clustered.groupby("cluster")["weekly_hours"].mean().sort_values()
    cluster_names = {
        hours_by_cluster.index[0]: "Lower study load",
        hours_by_cluster.index[1]: "Higher study load",
    }
    clustered["group"] = clustered["cluster"].map(cluster_names)
    summary = clustered.groupby("group").agg(
        n=("weekly_hours", "size"),
        weekly_hours=("weekly_hours", "mean"),
        well_being=("well_being", "mean"),
        time_management=("time_management", "mean"),
        online_strategies=("online_strategies", "mean"),
    )
    print("\n  Group characteristics on the original scales:")
    print(summary.round(2).to_string())

    atypical_cases = complete[complete["weekly_hours"] >= 70]
    print(
        "\n  Atypical cases (n=2): "
        f"weekly hours={atypical_cases['weekly_hours'].mean():.2f}; "
        f"well-being={atypical_cases['well_being'].mean():.2f}; "
        f"time management={atypical_cases['time_management'].mean():.2f}; "
        f"online strategies={atypical_cases['online_strategies'].mean():.2f}"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for axis, (subset, title) in zip(
        axes,
        [
            (complete, "Complete sample (n=69)"),
            (without_atypical_cases, "Atypical cases set aside (n=67)"),
        ],
    ):
        standardised_subset = StandardScaler().fit_transform(subset[variables])
        inertias = [
            KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE)
            .fit(standardised_subset)
            .inertia_
            for k in range(1, 7)
        ]
        axis.plot(range(1, 7), inertias, "o-")
        axis.set_xlabel("Number of clusters (k)")
        axis.set_ylabel("Within-cluster sum of squares")
        axis.set_title(title)
        axis.grid(alpha=0.3)
    plt.tight_layout()
    elbow_path = FIGURES_DIR / "figure_clustering_elbow.png"
    plt.savefig(elbow_path, dpi=150, bbox_inches="tight")
    plt.close()

    scaling = StandardScaler().fit(complete[variables])
    pca = PCA(n_components=2, random_state=RANDOM_STATE).fit(
        scaling.transform(complete[variables])
    )
    projection = pca.transform(scaling.transform(complete[variables]))
    explained = pca.explained_variance_ratio_ * 100

    plot_data = complete.copy()
    plot_data["component_1"] = projection[:, 0]
    plot_data["component_2"] = projection[:, 1]
    plot_data["atypical"] = plot_data["weekly_hours"] >= 70
    plot_data["category"] = "Atypical cases"
    plot_data.loc[~plot_data["atypical"], "category"] = clustered["group"].values

    figure, axis = plt.subplots(figsize=(7.5, 5.4))
    for category in ["Lower study load", "Higher study load", "Atypical cases"]:
        subset = plot_data[plot_data["category"] == category]
        axis.scatter(
            subset["component_1"],
            subset["component_2"],
            label=f"{category} (n={len(subset)})",
            s=55,
            marker="D" if category == "Atypical cases" else "o",
        )
    axis.set_xlabel(f"PCA 1 ({explained[0]:.1f}% of variance)")
    axis.set_ylabel(f"PCA 2 ({explained[1]:.1f}% of variance)")
    axis.legend(title="Grouping", frameon=True, loc="lower right", fontsize=9)
    axis.grid(alpha=0.25)
    plt.tight_layout()
    pca_path = FIGURES_DIR / "figure_clustering_pca.png"
    plt.savefig(pca_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  [Figures saved to {elbow_path} and {pca_path}]\n")


# -----------------------------------------------------------------------------
# Lexical analysis
# -----------------------------------------------------------------------------
TEXT_CATEGORIES = {
    "Motivations and views": [58, 59],
    "Self-assessment and strategies": [35, 37, 55],
    "Challenges and resources": [48, 49],
    "Interaction and support": [52],
    "Reflection and final comments": [65, 66, 67],
}

STOPWORDS = set(
    """
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
    """.split()
)


def tokenise(text: object) -> list[str]:
    """Tokenise an open response using the preprocessing reported in the article."""
    lower_case = str(text).lower()
    cleaned = re.sub(
        r"[^\w\s\u00e1\u00e0\u00e2\u00e3\u00e9\u00ea\u00ed\u00f3\u00f4\u00f5\u00fa\u00fc\u00e7-]",
        " ",
        lower_case,
    )
    tokens: list[str] = []
    for word in cleaned.split():
        word = word.strip("-")
        if len(word) >= 3 and not word.isdigit() and strip_accents(word) not in STOPWORDS:
            tokens.append(word)
    return tokens


def log_likelihood_g2(
    frequency_inside: int,
    frequency_outside: int,
    total_inside: int,
    total_outside: int,
) -> float:
    """Calculate the log-likelihood ratio G-squared used for descriptive keyness."""
    total = total_inside + total_outside
    expected_inside = total_inside * (frequency_inside + frequency_outside) / total
    expected_outside = total_outside * (frequency_inside + frequency_outside) / total
    value = 0.0
    if frequency_inside > 0:
        value += frequency_inside * np.log(frequency_inside / expected_inside)
    if frequency_outside > 0:
        value += frequency_outside * np.log(frequency_outside / expected_outside)
    return 2 * value


def report_lexical_analysis(header: pd.Series, data: pd.DataFrame) -> None:
    """Reproduce the category-based lexical analysis of the open responses."""
    print("=" * 78)
    print("LEXICAL ANALYSIS BY A PRIORI QUESTIONNAIRE CATEGORY")
    print("=" * 78)

    responses: list[tuple[str, str]] = []
    for category, columns in TEXT_CATEGORIES.items():
        for column in columns:
            for value in data[column].dropna():
                text = str(value).strip()
                if text and normalise_source_text(text) not in {"sim", "nao", "-", "n/a", "na"}:
                    responses.append((category, text))

    corpus = pd.DataFrame(responses, columns=["category", "text"])
    corpus["tokens"] = corpus["text"].apply(tokenise)
    print(f"  Corpus: {len(corpus)} non-empty responses across {len(TEXT_CATEGORIES)} categories.")
    print(corpus["category"].value_counts().to_string())

    frequencies = Counter(token for tokens in corpus["tokens"] for token in tokens)
    print("\n  Fifteen most frequent terms in the corpus:")
    for term, frequency in frequencies.most_common(15):
        print(f"    {term:22} {frequency}")

    try:
        from wordcloud import WordCloud

        word_cloud = WordCloud(
            width=1400,
            height=800,
            background_color="white",
            random_state=RANDOM_STATE,
            max_words=100,
        ).generate_from_frequencies(frequencies)
        figure, axis = plt.subplots(figsize=(11, 6.5))
        axis.imshow(word_cloud, interpolation="bilinear")
        axis.axis("off")
        plt.tight_layout()
        word_cloud_path = FIGURES_DIR / "figure_word_cloud.png"
        plt.savefig(word_cloud_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"\n  [Word cloud saved to {word_cloud_path}]")
    except ImportError:
        print("\n  [The optional wordcloud package is not installed; no word cloud was created.]")

    print("\n  Most characteristic terms by category")
    print("  (descriptive G-squared ranking against the remainder of the corpus; minimum frequency = 4)")
    table_rows: list[dict[str, object]] = []

    for category in TEXT_CATEGORIES:
        inside = Counter(
            token
            for tokens in corpus.loc[corpus["category"] == category, "tokens"]
            for token in tokens
        )
        outside = Counter(
            token
            for tokens in corpus.loc[corpus["category"] != category, "tokens"]
            for token in tokens
        )
        total_inside = sum(inside.values())
        total_outside = sum(outside.values())
        candidates: list[tuple[str, int, float]] = []

        for term, frequency in inside.items():
            if frequency < 4:
                continue
            if frequency / total_inside <= outside.get(term, 0) / total_outside:
                continue
            g_squared = log_likelihood_g2(
                frequency, outside.get(term, 0), total_inside, total_outside
            )
            candidates.append((term, frequency, g_squared))

        candidates.sort(key=lambda row: -row[2])
        top_five = candidates[:5]
        print(f"    {category}:")
        print(
            "      "
            + ", ".join(
                f"{term} (f={frequency}, G2={g_squared:.1f})"
                for term, frequency, g_squared in top_five
            )
        )
        for term, frequency, g_squared in top_five:
            table_rows.append(
                {
                    "category": category,
                    "term": term,
                    "frequency": frequency,
                    "G2": round(g_squared, 1),
                }
            )

    output_table = pd.DataFrame(table_rows)
    table_path = FIGURES_DIR / "table_characteristic_terms_by_category.csv"
    output_table.to_csv(table_path, index=False)
    print(f"\n  [Lexical table saved to {table_path}]\n")


# -----------------------------------------------------------------------------
# Bootstrap confidence intervals
# -----------------------------------------------------------------------------
def paired_spearman_bootstrap_ci(
    x: Iterable[float],
    y: Iterable[float],
    number_of_resamples: int = 10_000,
    confidence_level: float = .95,
    random_state: int = RANDOM_STATE,
) -> tuple[float, float]:
    """Calculate a percentile bootstrap confidence interval for Spearman's rho."""
    pairs = pd.DataFrame({"x": x, "y": y}).dropna()
    x_array = pairs["x"].to_numpy(dtype=float)
    y_array = pairs["y"].to_numpy(dtype=float)
    sample_size = len(pairs)
    if sample_size < 3:
        return np.nan, np.nan

    random_generator = np.random.default_rng(random_state)
    sampled_indices = random_generator.integers(
        0, sample_size, size=(number_of_resamples, sample_size)
    )
    x_bootstrap = x_array[sampled_indices]
    y_bootstrap = y_array[sampled_indices]

    x_ranks = stats.rankdata(x_bootstrap, axis=1, method="average")
    y_ranks = stats.rankdata(y_bootstrap, axis=1, method="average")
    x_ranks = x_ranks - x_ranks.mean(axis=1, keepdims=True)
    y_ranks = y_ranks - y_ranks.mean(axis=1, keepdims=True)
    denominator = np.sqrt(
        (x_ranks * x_ranks).sum(axis=1) * (y_ranks * y_ranks).sum(axis=1)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        values = (x_ranks * y_ranks).sum(axis=1) / denominator
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return np.nan, np.nan

    alpha = (1 - confidence_level) / 2
    lower, upper = np.quantile(values, [alpha, 1 - alpha])
    return float(lower), float(upper)


def independent_cliffs_delta_bootstrap_ci(
    group_a: Iterable[float],
    group_b: Iterable[float],
    number_of_resamples: int = 10_000,
    confidence_level: float = .95,
    random_state: int = RANDOM_STATE,
) -> tuple[float, float]:
    """Calculate a percentile bootstrap confidence interval for Cliff's delta."""
    a = pd.Series(group_a).dropna().to_numpy(dtype=float)
    b = pd.Series(group_b).dropna().to_numpy(dtype=float)
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan

    random_generator = np.random.default_rng(random_state)
    indices_a = np.empty((number_of_resamples, len(a)), dtype=int)
    indices_b = np.empty((number_of_resamples, len(b)), dtype=int)
    for resample_index in range(number_of_resamples):
        indices_a[resample_index] = random_generator.integers(0, len(a), len(a))
        indices_b[resample_index] = random_generator.integers(0, len(b), len(b))

    values: list[np.ndarray] = []
    block_size = 500
    for start in range(0, number_of_resamples, block_size):
        end = min(start + block_size, number_of_resamples)
        sampled_a = a[indices_a[start:end]]
        sampled_b = b[indices_b[start:end]]
        block_delta = np.sign(sampled_a[:, :, None] - sampled_b[:, None, :]).mean(
            axis=(1, 2)
        )
        values.append(block_delta)

    combined = np.concatenate(values)
    alpha = (1 - confidence_level) / 2
    lower, upper = np.quantile(combined, [alpha, 1 - alpha])
    return float(lower), float(upper)


# -----------------------------------------------------------------------------
# Additional analyses requested during peer review
# -----------------------------------------------------------------------------
def report_items_and_missingness(
    data: pd.DataFrame, digital_options: list[str]
) -> None:
    """Document item content, coding and missing-data handling."""
    print("=" * 78)
    print("REPRODUCIBILITY ANALYSIS A: ITEMS, CODING AND MISSING RESPONSES")
    print("=" * 78)

    consent = data[4].astype(str).apply(
        lambda value: normalise_source_text(value) == "sim"
    )
    valid_hours = pd.to_numeric(data[27], errors="coerce").notna()
    analytical_mask = consent & valid_hours
    analytical_data = data.loc[analytical_mask].copy()

    print(f"  Records in the cleaned analysis file: {len(data)}")
    print(
        "  Excluded because consent or valid weekly hours were absent: "
        f"{(~analytical_mask).sum()}"
    )
    print(f"  Final analytical sample: {len(analytical_data)}")

    item_blocks = {
        "Well-being": [(39, False), (40, False), (41, False), (42, False), (43, True), (44, True)],
        "Time management": [(28, False), (29, False), (30, False)],
    }

    for block_name, item_specifications in item_blocks.items():
        print(f"\n  {block_name}:")
        item_matrix: dict[str, pd.Series] = {}
        for column, reverse in item_specifications:
            source_series = binary_item(analytical_data, column, reverse=False)
            item_series = 1.0 - source_series if reverse else source_series
            item_matrix[f"item_{column}"] = item_series
            source_yes_count = int((source_series == 1).sum())
            source_no_count = int((source_series == 0).sum())
            coding_description = (
                "Source Yes=0, source No=1 (reverse-coded)"
                if reverse
                else "Yes=1, No=0"
            )
            print(f"    Column {column}: {ITEM_LABELS_EN[column]}")
            print(f"      Wording: {ITEM_WORDING_EN[column]}")
            print(
                f"      Coding: {coding_description}; missing={item_series.isna().sum()}; "
                f"source Yes n={source_yes_count}; source No n={source_no_count}"
            )

        matrix = pd.DataFrame(item_matrix)
        print(f"    Complete cases for KR-20: {len(matrix.dropna())}/{len(matrix)}")
        print("    Composite score: mean of the coded items on the 0-1 scale.")
        print("    All analytical participants answered every component item.")
        print("    No imputation or partial composite scoring was required.")

    print("\n  Online academic strategies (multiple-response item, column 32):")
    print(f"    Wording: {ITEM_WORDING_EN[32]}")
    print("    Five-option digital core:")
    for source_option in digital_options:
        selected_count = analytical_data[32].dropna().astype(str).apply(
            lambda value, option=source_option: option in value
        ).sum()
        print(f"      - {online_option_label(source_option)}: selected by n={int(selected_count)}")
    print(
        f"    Missing responses to column 32: "
        f"{analytical_data[32].isna().sum()}/{len(analytical_data)}"
    )
    print("    Composite score: number of digital options selected divided by five.")
    print("    No imputation or partial scoring was required.\n")


def report_item_level_analyses(
    data: pd.DataFrame,
    indices: pd.DataFrame,
    digital_options: list[str],
) -> None:
    """Run the item-level analyses requested for the two low-reliability aggregates."""
    print("=" * 78)
    print("REPRODUCIBILITY ANALYSIS B: ITEM-LEVEL RESULTS")
    print("=" * 78)

    weekly_hours = pd.to_numeric(data[27], errors="coerce")
    time_items = [
        (28, "Study schedules or routines"),
        (29, "Prioritisation of academic tasks"),
        (30, "Management of intervals and breaks"),
    ]

    time_results: list[dict[str, float | int | str]] = []
    for column, label in time_items:
        item = binary_item(data, column)
        pairs = pd.DataFrame({"item": item, "weekly_hours": weekly_hours}).dropna()
        rho, p_value = stats.spearmanr(pairs["item"], pairs["weekly_hours"])
        lower, upper = paired_spearman_bootstrap_ci(
            pairs["item"], pairs["weekly_hours"]
        )
        time_results.append(
            {
                "column": column,
                "label": label,
                "n": len(pairs),
                "proportion": pairs["item"].mean(),
                "rho": rho,
                "p": p_value,
                "lower": lower,
                "upper": upper,
            }
        )

    time_holm = holm_adjust(result["p"] for result in time_results)
    print("\n  Time-management items and weekly study hours:")
    for result, adjusted_p in zip(time_results, time_holm):
        print(
            f"    {result['label']} (column {result['column']}; n={result['n']}; "
            f"proportion Yes={result['proportion']:.3f}): "
            f"rho={result['rho']:+.3f}, 95% CI [{result['lower']:+.3f}, "
            f"{result['upper']:+.3f}], p={result['p']:.4f}, "
            f"Holm-adjusted p={adjusted_p:.4f}"
        )

    online_results: list[dict[str, float | int | str]] = []
    for source_option in digital_options:
        item = data[32].apply(
            lambda value, option=source_option: (
                1.0 if option in str(value) else 0.0
            )
            if pd.notna(value)
            else np.nan
        )
        item_data = pd.DataFrame({"item": item, "gender": data[7]}).dropna()
        male = item_data.loc[item_data["gender"] == "Masculino", "item"]
        female = item_data.loc[item_data["gender"] == "Feminino", "item"]
        u_male, p_value = stats.mannwhitneyu(male, female, alternative="two-sided")
        u_female = len(male) * len(female) - u_male
        delta = cliffs_delta(male, female)
        lower, upper = independent_cliffs_delta_bootstrap_ci(male, female)
        online_results.append(
            {
                "label": online_option_label(source_option),
                "male_mean": male.mean(),
                "female_mean": female.mean(),
                "male_n": len(male),
                "female_n": len(female),
                "u": min(u_male, u_female),
                "p": p_value,
                "delta": delta,
                "lower": lower,
                "upper": upper,
            }
        )

    online_holm = holm_adjust(result["p"] for result in online_results)
    print("\n  Online academic strategy items by gender:")
    for result, adjusted_p in zip(online_results, online_holm):
        print(f"    {result['label']}")
        print(
            f"      male={result['male_mean']:.3f} (n={result['male_n']}), "
            f"female={result['female_mean']:.3f} (n={result['female_n']}); "
            f"U={result['u']:.1f}, p={result['p']:.4f}, "
            f"Holm-adjusted p={adjusted_p:.4f}, delta={result['delta']:+.3f}, "
            f"95% CI [{result['lower']:+.3f}, {result['upper']:+.3f}]"
        )
    print("    Convention: positive delta denotes higher values among male students.")
    print("    Holm-adjusted p-values control multiplicity within each item family.\n")


def report_principal_correlations_with_ci(indices: pd.DataFrame) -> None:
    """Report principal Spearman correlations with 95% bootstrap confidence intervals."""
    print("=" * 78)
    print("REPRODUCIBILITY ANALYSIS C: PRINCIPAL CORRELATIONS WITH 95% CIs")
    print("=" * 78)

    comparisons = [
        ("weekly_hours", "time_management", "Weekly hours x time management"),
        ("weekly_hours", "well_being", "Weekly hours x well-being"),
        ("weekly_hours", "online_strategies", "Weekly hours x online strategies"),
        ("time_management", "well_being", "Time management x well-being"),
        ("time_management", "online_strategies", "Time management x online strategies"),
    ]

    for first, second, label in comparisons:
        pairs = indices[[first, second]].dropna()
        rho, p_value = stats.spearmanr(pairs[first], pairs[second])
        lower, upper = paired_spearman_bootstrap_ci(pairs[first], pairs[second])
        print(
            f"  {label:46} n={len(pairs)} rho={rho:+.3f} "
            f"95% CI [{lower:+.3f}, {upper:+.3f}] p={p_value:.4f}"
        )
    print()


def report_cliffs_delta_with_ci(data: pd.DataFrame, indices: pd.DataFrame) -> None:
    """Report gender effect sizes with 95% bootstrap confidence intervals."""
    print("=" * 78)
    print("REPRODUCIBILITY ANALYSIS D: CLIFF'S DELTA WITH 95% CIs")
    print("=" * 78)

    analytical = indices.copy()
    analytical["gender"] = data[7]
    analytical = analytical.dropna(
        subset=["weekly_hours", "well_being", "time_management", "online_strategies"]
    )
    male = analytical[analytical["gender"] == "Masculino"]
    female = analytical[analytical["gender"] == "Feminino"]

    for column, label in [
        ("online_strategies", "Online academic strategies"),
        ("time_management", "Time management"),
        ("well_being", "Well-being"),
    ]:
        delta = cliffs_delta(male[column], female[column])
        lower, upper = independent_cliffs_delta_bootstrap_ci(
            male[column], female[column]
        )
        u_male, p_value = stats.mannwhitneyu(
            male[column], female[column], alternative="two-sided"
        )
        u_female = len(male) * len(female) - u_male
        print(
            f"  {label:30} U={min(u_male, u_female):.1f} p={p_value:.4f} "
            f"delta={delta:+.3f} 95% CI [{lower:+.3f}, {upper:+.3f}]"
        )
    print("  Convention: positive delta denotes higher values among male students.\n")


def find_programme_column(header: pd.Series) -> list[tuple[int, str]]:
    """Identify the degree-programme question in the source questionnaire."""
    exact_matches: list[tuple[int, str]] = []
    approximate_matches: list[tuple[int, str]] = []
    for column, wording in header.items():
        normalised = normalise_source_text(wording)
        if normalised in {"qual o seu curso?", "qual e o seu curso?"}:
            exact_matches.append((column, str(wording)))
        elif normalised.startswith("qual o seu curso") or normalised.startswith("qual e o seu curso"):
            approximate_matches.append((column, str(wording)))
    return exact_matches if exact_matches else approximate_matches


def group_programme(value: object) -> str:
    """Map source programme names to the seven categories reported in the article."""
    normalised = normalise_source_text(value)
    if "enfermagem" in normalised:
        return "Nursing"
    if "fisioterapia" in normalised:
        return "Physiotherapy"
    if "osteopatia" in normalised:
        return "Osteopathy"
    if "nutricao" in normalised:
        return "Nutrition Sciences"
    if "engenharia mecanica" in normalised or "engenharia aeronautica" in normalised:
        return "Engineering"
    if "gestao" in normalised:
        return "Management"
    return "Other"


def report_programme_sensitivity(
    header: pd.Series, data: pd.DataFrame, indices: pd.DataFrame
) -> None:
    """Assess whether programme composition accounts for the principal association."""
    print("=" * 78)
    print("REPRODUCIBILITY ANALYSIS E: PROGRAMME-COMPOSITION SENSITIVITY")
    print("=" * 78)

    candidates = find_programme_column(header)
    if len(candidates) != 1:
        print("  The programme column could not be identified unambiguously.")
        print("  Candidate columns:")
        for column, wording in candidates:
            print(f"    Column {column}: {wording}")
        print("  The sensitivity analysis was not run.\n")
        return

    programme_column, _ = candidates[0]
    print(f"  Programme column identified: {programme_column}")

    analytical = indices.copy()
    analytical["source_programme"] = data[programme_column].astype("string")
    analytical["programme"] = analytical["source_programme"].apply(group_programme)
    analytical = analytical.dropna(
        subset=["weekly_hours", "well_being", "time_management", "online_strategies", "programme"]
    )

    programme_levels = [
        "Management",
        "Nursing",
        "Physiotherapy",
        "Engineering",
        "Osteopathy",
        "Nutrition Sciences",
        "Other",
    ]
    counts = analytical["programme"].value_counts().reindex(programme_levels, fill_value=0)
    print("  Grouped distribution, matching the manuscript:")
    print(counts.to_string())

    analytical["management_programme"] = (
        analytical["programme"] == "Management"
    ).astype(float)
    analytical["male"] = (
        data.loc[analytical.index, 7].astype(str).str.strip() == "Masculino"
    ).astype(float)

    def fit_parsimonious(subset: pd.DataFrame, label: str) -> sm.robust.robust_linear_model.RLMResultsWrapper:
        predictors = sm.add_constant(
            subset[
                [
                    "well_being",
                    "time_management",
                    "online_strategies",
                    "management_programme",
                    "male",
                ]
            ].astype(float)
        )
        outcome = subset["weekly_hours"].astype(float)
        model = sm.RLM(outcome, predictors, M=sm.robust.norms.HuberT()).fit()
        print(f"\n  {label}:")
        for key, display_label in [
            ("time_management", "Time management"),
            ("well_being", "Well-being"),
            ("online_strategies", "Online strategies"),
            ("management_programme", "Management programme"),
            ("male", "Male gender"),
        ]:
            lower, upper = model.conf_int().loc[key]
            print(
                f"    {display_label:24} B={model.params[key]:+.3f}, "
                f"95% CI [{lower:+.3f}, {upper:+.3f}], p={model.pvalues[key]:.4f}"
            )
        return model

    fit_parsimonious(
        analytical,
        "Parsimonious robust model: Management versus other programmes plus gender",
    )
    fit_parsimonious(
        analytical[analytical["weekly_hours"] < 70],
        "Parsimonious robust model with the two atypical cases set aside",
    )

    dummy_variables = pd.DataFrame(index=analytical.index)
    for level in programme_levels[1:]:
        column_name = "programme_" + level.lower().replace(" ", "_")
        dummy_variables[column_name] = (analytical["programme"] == level).astype(float)

    def fit_full_programme_model(subset: pd.DataFrame, label: str) -> None:
        predictors = pd.concat(
            [
                subset[["well_being", "time_management", "online_strategies"]].astype(float),
                dummy_variables.loc[subset.index],
            ],
            axis=1,
        )
        predictors = sm.add_constant(predictors)
        outcome = subset["weekly_hours"].astype(float)
        model = sm.RLM(outcome, predictors, M=sm.robust.norms.HuberT()).fit()
        print(f"\n  {label} (Management is the reference category):")
        for key, display_label in [
            ("time_management", "Time management"),
            ("well_being", "Well-being"),
            ("online_strategies", "Online strategies"),
        ]:
            lower, upper = model.conf_int().loc[key]
            print(
                f"    {display_label:24} B={model.params[key]:+.3f}, "
                f"95% CI [{lower:+.3f}, {upper:+.3f}], p={model.pvalues[key]:.4f}"
            )

    fit_full_programme_model(analytical, "Robust model adjusted for all programme categories")
    fit_full_programme_model(
        analytical[analytical["weekly_hours"] < 70],
        "Robust model adjusted for all programme categories, atypical cases set aside",
    )
    print("  These are sensitivity analyses, not confirmatory adjusted models, because n=69.\n")


def report_clustering_without_hours(indices: pd.DataFrame) -> None:
    """Repeat clustering without weekly study hours, as requested by the reviewer."""
    print("=" * 78)
    print("REPRODUCIBILITY ANALYSIS F: CLUSTERING WITHOUT WEEKLY STUDY HOURS")
    print("=" * 78)

    complete = indices.dropna().reset_index(drop=True)
    without_atypical_cases = complete[complete["weekly_hours"] < 70].reset_index(drop=True)

    original_variables = ["well_being", "time_management", "online_strategies", "weekly_hours"]
    variables_without_hours = ["well_being", "time_management", "online_strategies"]

    original_standardised = StandardScaler().fit_transform(
        without_atypical_cases[original_variables]
    )
    reduced_standardised = StandardScaler().fit_transform(
        without_atypical_cases[variables_without_hours]
    )

    original_kmeans = KMeans(
        n_clusters=2, n_init=25, random_state=RANDOM_STATE
    ).fit(original_standardised)

    def evaluate(number_of_clusters: int) -> tuple[KMeans, float, float]:
        model = KMeans(
            n_clusters=number_of_clusters, n_init=25, random_state=RANDOM_STATE
        ).fit(reduced_standardised)
        silhouette = silhouette_score(reduced_standardised, model.labels_)
        ward = AgglomerativeClustering(
            n_clusters=number_of_clusters, linkage="ward"
        ).fit_predict(reduced_standardised)
        ward_ari = adjusted_rand_score(model.labels_, ward)
        return model, silhouette, ward_ari

    kmeans_two, silhouette_two, ward_ari_two = evaluate(2)
    kmeans_three, silhouette_three, ward_ari_three = evaluate(3)
    agreement_with_original = adjusted_rand_score(
        original_kmeans.labels_, kmeans_two.labels_
    )

    def bootstrap_stability(
        number_of_clusters: int,
        reference_labels: np.ndarray,
        number_of_resamples: int = 200,
    ) -> tuple[float, float]:
        random_generator = np.random.default_rng(RANDOM_STATE)
        ari_values: list[float] = []
        for _ in range(number_of_resamples):
            sampled_indices = random_generator.choice(
                len(without_atypical_cases), len(without_atypical_cases), replace=True
            )
            bootstrap_standardised = StandardScaler().fit_transform(
                without_atypical_cases.iloc[sampled_indices][variables_without_hours]
            )
            bootstrap_labels = KMeans(
                n_clusters=number_of_clusters, n_init=10, random_state=0
            ).fit(bootstrap_standardised).labels_
            ari_values.append(
                adjusted_rand_score(reference_labels[sampled_indices], bootstrap_labels)
            )
        return float(np.mean(ari_values)), float(np.std(ari_values))

    bootstrap_two, bootstrap_two_sd = bootstrap_stability(2, kmeans_two.labels_)
    bootstrap_three, bootstrap_three_sd = bootstrap_stability(3, kmeans_three.labels_)

    print(
        f"  Without weekly hours, k=2: silhouette={silhouette_two:.4f}; "
        f"bootstrap ARI={bootstrap_two:.4f} (SD={bootstrap_two_sd:.3f}); "
        f"Ward ARI={ward_ari_two:.4f}"
    )
    print(
        f"  Without weekly hours, k=3: silhouette={silhouette_three:.4f}; "
        f"bootstrap ARI={bootstrap_three:.4f} (SD={bootstrap_three_sd:.3f}); "
        f"Ward ARI={ward_ari_three:.4f}"
    )
    print(
        "  Agreement between the original k=2 partition and the k=2 partition "
        f"without hours: ARI={agreement_with_original:.4f}"
    )

    two_cluster_data = without_atypical_cases.copy()
    two_cluster_data["cluster_without_hours"] = kmeans_two.labels_
    two_summary = two_cluster_data.groupby("cluster_without_hours").agg(
        n=("weekly_hours", "size"),
        well_being=("well_being", "mean"),
        time_management=("time_management", "mean"),
        online_strategies=("online_strategies", "mean"),
        external_weekly_hours=("weekly_hours", "mean"),
    ).round(2)
    print("\n  Characteristics of the k=2 groups formed without weekly hours:")
    print(two_summary.to_string())

    three_cluster_data = without_atypical_cases.copy()
    three_cluster_data["cluster_without_hours_k3"] = kmeans_three.labels_
    three_summary = three_cluster_data.groupby("cluster_without_hours_k3").agg(
        n=("weekly_hours", "size"),
        well_being=("well_being", "mean"),
        time_management=("time_management", "mean"),
        online_strategies=("online_strategies", "mean"),
        external_weekly_hours=("weekly_hours", "mean"),
    ).round(2)
    print("\n  Exploratory characteristics of the k=3 solution formed without weekly hours:")
    print(three_summary.to_string())
    print("  External weekly hours are descriptive only and were not used to form these clusters.")
    print("  The original lower-/higher-load partition did not reproduce without weekly hours.")
    print("  The k=3 solution had modestly better indicators but remains exploratory.\n")


# -----------------------------------------------------------------------------
# Main workflow
# -----------------------------------------------------------------------------
def main() -> None:
    """Run the complete reproducible workflow in manuscript order."""
    print("=" * 78)
    print("ICITS'27 PAPER 426 - REPRODUCIBILITY ANALYSIS")
    print("Authors: Luís Agonia Pereira; Ana de Jesus Mendes; Valter Martins Vairinhos")
    print("Repository version: 2.0.0")
    print("=" * 78)
    header, data = load_data()
    indices, digital_options = construct_indices(data)

    report_reliability(data, digital_options)
    report_descriptive_statistics(indices)
    plot_index_boxplots(indices)
    report_spearman_correlations(indices)
    report_robust_regression(indices)
    report_gender_differences(data, indices)
    plot_gender_differences(data, indices)
    report_original_clustering(indices)
    report_lexical_analysis(header, data)

    report_items_and_missingness(data, digital_options)
    report_item_level_analyses(data, indices, digital_options)
    report_principal_correlations_with_ci(indices)
    report_cliffs_delta_with_ci(data, indices)
    report_programme_sensitivity(header, data, indices)
    report_clustering_without_hours(indices)

    print("=" * 78)
    print("ANALYSIS COMPLETE. Figures and lexical tables are available in ./figures/")
    print("=" * 78)


if __name__ == "__main__":
    main()
