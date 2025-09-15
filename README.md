# Questionário Limpo - Hábitos de Estudo (Universidade Atlântica)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.17127602.svg)](https://doi.org/10.5281/zenodo.17127602)

Versão atual: **v1.0.1 (15/09/2025)**  
DOI: [10.5281/zenodo.17127602](https://doi.org/10.5281/zenodo.17127602)


Este repositório contém o **dataset final (limpo)** utilizado no estudo *"Entre o Presencial e o Online: Análise dos Hábitos de Estudo e a Possibilidade de um Modelo Híbrido"*, realizado com estudantes da Universidade Atlântica (Oeiras, Portugal).  
O objetivo do estudo foi compreender hábitos de estudo, preferências de aprendizagem e perceções sobre a viabilidade de um **modelo híbrido de ensino**.

> **Nota ética:** Todos os dados foram anonimizados e tratados de forma a garantir a confidencialidade dos participantes. Este repositório contém apenas a base limpa, sem identificadores pessoais.

---

## 📂 Estrutura do repositório

| Ficheiro | Descrição |
|----------|------------|
| `Questionario_Limpo.xlsx` | Base de dados final limpa, pronta para análise. |
| `CODEBOOK.md` *(em breve)* | Dicionário de dados: descrição de todas as variáveis, escalas e codificação. |
| `LICENSE` | Texto completo da licença **CC BY-NC 4.0**. |
| `CITATION.cff` | Informação estruturada para citação do repositório. |

---

## 🔗 Acesso rápido ao dataset

Para carregar o ficheiro diretamente no **Python (Pandas)**:

```python
import pandas as pd
url = "https://raw.githubusercontent.com/luisagoniapereira/questionario-habitos-estudo/main/Questionario_Limpo.xlsx"
df = pd.read_excel(url, sheet_name=0, header=1)
df.head()
