# Reproducibility Analysis Report
## Version 2.0.0

**Article:** *Student Engagement in Technology-Mediated Hybrid Higher Education: An Exploratory Institutional Case Study*  
**Authors:** Luís Agonia Pereira; Ana de Jesus Mendes; Valter Martins Vairinhos  
**Analytical sample:** 69 undergraduate students  
**Analysis date:** 14 November 2026  
**Language:** British English

## 1. Dataset validation and missing-data handling

The cleaned workbook contains 70 records. One record lacks informed consent and valid weekly study hours and is excluded. The final analytical sample therefore contains 69 participants, matching the manuscript.

All quantitative variables used in the article are complete for the 69 analytical participants:

- well-being: six complete items for 69/69 participants;
- time management: three complete items for 69/69 participants;
- online academic strategies: the multiple-response item is complete for 69/69 participants;
- weekly study hours, gender and degree programme: complete for 69/69 participants.

No imputation, pairwise reconstruction or partial composite scoring was required. The well-being and time-management scores are the means of their binary component items on a 0-1 scale. The two fatigue items are reverse-coded. The online academic-strategy score is the proportion of five selected digital practices.

The reliability coefficients were reproduced exactly:

- well-being: KR-20 = .721;
- time management: KR-20 = .429;
- online academic strategies: KR-20 = .477.

The latter two measures should continue to be described as exploratory behavioural aggregates rather than validated unidimensional scales.

## 2. Item-level analysis of time management

All three items show a positive association with weekly study hours, although none remains statistically significant after Holm adjustment.

| Item | Proportion answering Yes | Spearman's rho | Bootstrap 95% CI | p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|
| Study schedules or routines | .594 | .234 | [.002, .458] | .053 | .159 |
| Prioritisation of academic tasks | .855 | .222 | [.029, .397] | .066 | .159 |
| Management of intervals and breaks | .768 | .152 | [-.099, .388] | .211 | .211 |

The item-level pattern is directionally consistent. The association of the composite time-management score with weekly study hours is therefore not attributable to one discordant item. The low KR-20 nevertheless requires a cautious, descriptive interpretation.

## 3. Item-level analysis of online academic strategies by gender

The aggregate gender difference is concentrated mainly in two practices rather than being uniform across the five digital strategies.

| Strategy | Male proportion | Female proportion | Cliff's delta | Bootstrap 95% CI | p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|---:|
| Mind maps or diagrams | .226 | .316 | -.090 | [-.298, .124] | .413 | .826 |
| Studying with peers in virtual learning communities | .516 | .158 | .358 | [.144, .566] | .002 | .008 |
| Exercise completion | .613 | .289 | .323 | [.095, .537] | .008 | .030 |
| Text summaries | .742 | .763 | -.021 | [-.229, .181] | .846 | .846 |
| Online resources such as videos, manuals and forums | .806 | .579 | .228 | [.014, .430] | .046 | .138 |

Positive delta values denote higher values among male students. After Holm adjustment, the differences remain for virtual peer study and exercise completion. The online-resource difference is weaker and does not remain significant after adjustment. There is no evidence of a gender difference in mind maps or text summaries.

## 4. Confidence intervals for the principal correlations

| Association | Spearman's rho | Bootstrap 95% CI | p |
|---|---:|---:|---:|
| Weekly study hours x time management | .326 | [.089, .535] | .006 |
| Weekly study hours x well-being | .211 | [-.045, .450] | .083 |
| Weekly study hours x online academic strategies | -.038 | [-.288, .217] | .759 |
| Time management x well-being | .240 | [.008, .451] | .047 |
| Time management x online academic strategies | .295 | [.062, .513] | .014 |

The principal association between time management and weekly study hours has a fully positive confidence interval. The intervals for the associations of weekly hours with well-being and online strategies include zero.

## 5. Confidence intervals for gender effect sizes

| Aggregate | Cliff's delta | Bootstrap 95% CI | p |
|---|---:|---:|---:|
| Online academic strategies | .385 | [.133, .621] | .005 |
| Time management | -.016 | [-.274, .239] | .906 |
| Well-being | -.018 | [-.285, .256] | .903 |

## 6. Sensitivity to programme composition and gender

### 6.1 Parsimonious adjusted model

A robust regression was estimated with the three behavioural aggregates, an indicator of membership of a Management programme and gender. This specification addresses the over-representation of Management students without introducing six programme indicators into a sample of 69.

**All 69 participants:**

- time management: B = 10.235, 95% CI [1.678, 18.792], p = .019;
- well-being: B = 6.602, 95% CI [-1.137, 14.341], p = .095;
- online academic strategies: B = -5.669, 95% CI [-15.279, 3.940], p = .248;
- Management-programme membership: B = 1.855, p = .456;
- male gender: B = .427, p = .865.

**Two atypical high-load cases set aside:**

- time management: B = 9.953, 95% CI [1.760, 18.146], p = .017;
- well-being: B = 9.525, 95% CI [1.834, 17.215], p = .015;
- online academic strategies: B = -2.733, p = .569;
- Management-programme membership: B = 1.682, p = .483;
- male gender: B = -.064, p = .979.

### 6.2 Model using all seven programme categories

The programme distribution reproduces the manuscript: Management 30, Nursing 18, Physiotherapy 8, Engineering 4, Osteopathy 4, Nutrition Sciences 3 and Other 2.

With all cases, time management remains associated with weekly hours, B = 12.406, 95% CI [3.965, 20.847], p = .004. With the two atypical cases set aside, the association remains, B = 13.248, 95% CI [5.256, 21.240], p = .001; well-being is also associated with weekly hours, B = 9.058, 95% CI [1.869, 16.246], p = .014.

The principal time-management result is not explained by the concentration of Management students or by gender. Because of the sample size and small programme subgroups, these models should be presented as sensitivity analyses rather than confirmatory adjusted models.

## 7. Clustering without weekly study hours

The original clustering used well-being, time management, online academic strategies and weekly study hours. The reviewer-requested sensitivity analysis repeated the procedure using only the three behavioural aggregates.

| Solution without weekly hours | Silhouette | Bootstrap ARI | ARI with Ward |
|---|---:|---:|---:|
| k = 2 | .265 | .372 | .176 |
| k = 3 | .305 | .594 | .709 |

Agreement between the original k = 2 partition and the new k = 2 partition is ARI = .050, which is effectively negligible.

In the k = 2 solution formed without weekly hours, the groups have external mean study loads of 12.23 and 13.65 hours. They no longer represent a clear lower- versus higher-load distinction. The k = 3 solution has modestly better validation indicators but remains exploratory:

| Group | n | Well-being | Time management | Online strategies | Weekly hours, descriptive only |
|---|---:|---:|---:|---:|---:|
| 1 | 29 | .36 | .87 | .72 | 13.10 |
| 2 | 22 | .75 | .83 | .34 | 16.32 |
| 3 | 16 | .28 | .40 | .32 | 8.31 |

The original lower-/higher-load partition was strongly influenced by including weekly study hours among the clustering variables. The clustering section should remain strictly descriptive and should state that the original partition did not reproduce when weekly hours were excluded.

## 8. Implications for the final manuscript

1. Retain the principal conclusion concerning time management, now supported by confidence intervals and programme-composition sensitivity analyses.
2. Describe time management and online academic strategies as exploratory behavioural aggregates, not psychometrically validated unidimensional scales.
3. Report the component items, response formats, coding, reverse-coding and score-construction rules in the Instrument section.
4. State that all quantitative variables were complete for the 69 analytical participants and that no imputation or partial scoring was required.
5. Explain that the gender difference in online strategies is concentrated in two practices rather than representing a uniform difference across all five items.
6. Add 95% confidence intervals to the principal correlations and Cliff's delta estimates.
7. Include the parsimonious programme-and-gender sensitivity model in the main text; retain the seven-category model as an additional robustness check.
8. Reduce the interpretative weight of the clustering and report its sensitivity to excluding weekly study hours.
9. Do not publish verbatim participant excerpts unless the consent documentation explicitly permits verbatim quotation.
10. Keep hybrid provision clearly framed as the institutional context rather than an intervention whose effect was estimated.

## 9. Recommended British-English wording

### Missing data and score construction

> All variables used in the quantitative analyses were complete for the 69 participants. No imputation was performed and no partial composite scores were required. The well-being and time-management indices were calculated as the mean of their dichotomously coded component items, after reverse-coding the two fatigue items. The online academic strategies index represented the proportion of five digital practices selected by each participant.

### Item-level time-management results

> Item-level analyses showed positive associations with weekly study hours for all three time-management behaviours, although none remained statistically significant after Holm adjustment. The strongest item-level associations concerned the use of study schedules and the prioritisation of academic tasks. This pattern suggests that the composite association was not attributable to a single item with a discordant direction, but the low internal consistency of the aggregate still warrants a cautious, descriptive interpretation.

### Gender difference in online strategies

> The gender difference in the online academic strategies aggregate was concentrated in two practices. Male students more frequently reported studying with peers in virtual learning communities and completing exercises, with both differences remaining after Holm adjustment. No gender differences were evident for mind maps or text summaries, and the difference in online-resource use did not remain significant after adjustment.

### Programme-composition sensitivity

> In a parsimonious sensitivity model that additionally included Management-programme membership and gender, time management remained positively associated with weekly study hours. Neither Management-programme membership nor gender was associated with the outcome. The result was similar after the two atypical high-load cases were set aside and in a model using all seven programme categories.

### Clustering sensitivity

> When weekly study hours were excluded from cluster formation, the original lower- versus higher-load partition did not reproduce. Agreement with the original partition was negligible, and the two-cluster solution formed without weekly hours showed similar external mean study loads across groups. A three-cluster solution produced modestly better validation indicators but remained exploratory. The cluster results are therefore retained as descriptive, variable-dependent groupings rather than stable student typologies.
