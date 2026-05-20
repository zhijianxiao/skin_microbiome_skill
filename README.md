# Skin Microbiome Skill

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Non-human skin microbiome literature search tool.**

Enter a species name (Chinese or English) — the skill searches PubMed for skin microbiome studies on that animal host, filters out human research, extracts metagenomic BioProject IDs, identifies anatomical sampling sites from abstracts, and exports everything to a formatted Excel file.

---

## How It Works

```
User Input                  PubMed                     ENA                      Output
───────────              ───────────               ───────────               ──────────
 Species name                                                           ┌─────────────────┐
  ↓                        ┌──────────┐            ┌──────────┐         │  文献标题        │
 SpeciesManager            │ Search   │            │ ENAClient│         │  作者            │
 .normalize()              │ Engine   │            │          │         │  年份            │
  ↓                        │          │            │ Resolve  │         │  DOI             │
 Latin name                │ PubMed   │──BioProj──→│ PRJNAxxx │         │  实验物种         │
  ↓                        │ query:   │            │ PRJEBxxx │         │  宏基因组数据集    │
 PubMed query              │ (skin    │            │          │         │  取样部位         │
  ↓                        │  microbi │            └──────────┘         └─────────────────┘
 Articles ───2nd filter──→ │  ome)    │                                        Excel
 (non-human, skin-related) │ AND      │
                            │ (Equus)  │
 Sampling site extraction   │ NOT human│
                            └──────────┘
```

1. **Species normalization** — Chinese or English name → English common name → Latin scientific name
2. **PubMed query construction** — `("skin microbiome" OR "cutaneous microbiota" OR "dermal microbiome") AND ("{species}") NOT human`
3. **Secondary filtering** — excludes articles mentioning human patients/volunteers; requires skin-related terms in title or abstract
4. **Sampling site extraction** — 40+ regex patterns identify anatomical sites (ear, nose, paw, tail, hoof, wing, fin, etc.) from abstracts
5. **BioProject resolution** — extracts PRJNAxxx / PRJEBxxx metagenomic dataset IDs and resolves descriptions via ENA API
6. **Excel export** — 7 fixed columns with auto-filter, freeze panes; missing values marked `N/A`

---

## Installation

### Prerequisites

- **Conda** (Miniconda or Anaconda) — required by install scripts
- **Python ≥ 3.9** — included in Conda environment
- **NCBI email** — required by PubMed API; [register here](https://www.ncbi.nlm.nih.gov/account/) if you don't have one
- **NCBI API key** (optional) — increases rate limit from 3 to 10 requests/sec

### Linux / macOS

```bash
# 1. Clone the repository
git clone https://github.com/your-org/skin_microbiome_skill.git
cd skin_microbiome_skill

# 2. Run the install script (creates Conda env + installs dependencies)
bash scripts/install.sh

# 3. Activate the environment
conda activate skin_microbiome

# 4. Edit your NCBI email in config.yaml
#    Replace user@example.com with your email

# 5. Verify
skin-microbiome
```

### Windows (PowerShell)

```powershell
# 1. Clone the repository
git clone https://github.com/your-org/skin_microbiome_skill.git
cd skin_microbiome_skill

# 2. Run the install script
.\scripts\install.ps1

# 3. Activate the environment
conda activate skin_microbiome

# 4. Edit your NCBI email in config.yaml
#    Replace user@example.com with your email

# 5. Verify
skin-microbiome
```

### Manual Installation (without Conda)

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

---

## Quick Start

### Interactive Mode

```bash
$ skin-microbiome
```

```
============================================================
  Non-Human Skin Microbiome Literature Search
  Platform: linux
============================================================

  Species name (Chinese or English, e.g. 马 / mouse): 马

  Normalized: 马 → Horse → Equus caballus

  Extra keywords (optional, Enter to skip):

  Searching PubMed (max 100)…
  Query: (skin microbiome) AND (Equus caballus) NOT human
  → 23 articles after non-human skin filter.

────────────────────────────────────────────────────────────
  Preview — top 10 of 23 articles
────────────────────────────────────────────────────────────
  [ 1] Characterization of the equine skin microbiome in healthy horses
       year=2025  site=Ear  bioproject=PRJNA123456
  [ 2] Cutaneous fungal diversity in thoroughbred horses
       year=2024  site=Back  bioproject=PRJEB990011
  ...
────────────────────────────────────────────────────────────

  Options: [Enter] continue  [r] refine keywords  [q] quit
  >

  Resolving metagenomic BioProject IDs…
  BioProjects found in 8/23 articles.

  Export format:
    [1] Excel (.xlsx) — default
    [2] CSV
    [3] JSON
    [4] Skip
  > 1

  Exported to: ./output/Equus_caballus_20260520_143022.xlsx
```

### Scripting (Non-interactive)

```python
from skill import SkinMicrobiomeSkill

skill = SkinMicrobiomeSkill(config_path="config.yaml")

# One-liner: search + filter + export
articles = skill.run_pipeline(
    species="鼠",
    extra_keywords="atopic dermatitis",
    max_results=50,
    export_format="xlsx",
)

# Inspect results
for art in articles:
    print(f"[{art['sampling_site']}] {art['title'][:60]}...")
```

### CLI Commands

```bash
# List all supported species
skin-microbiome list-species

# Search from command line
skin-microbiome search 马
skin-microbiome search mouse "atopic dermatitis"
```

---

## Output Format

The Excel file contains exactly **7 columns**:

| Column | Example Value | Notes |
|--------|--------------|-------|
| 文献标题 | Characterization of the equine skin microbiome in healthy horses | Full PubMed title |
| 作者 | Smith J; Brown A | Semicolon-separated, max 10 shown |
| 年份 | 2025 | Publication year |
| DOI | 10.1111/vde.13001 | `N/A` if not available |
| 实验物种 | Equus caballus | Latin name from species.py |
| 宏基因组数据集 | PRJNA123456; PRJEB998877 | Semicolon-separated BioProjects, or `N/A` |
| 取样部位 | Ear | Anatomical site from abstract, or `N/A` |

Features of the output Excel:
- **Auto-filter** on all columns — sort/filter by species, year, sampling site, etc.
- **Frozen header row** — always visible when scrolling
- **Text wrapping** on the title column
- **`N/A` placeholder** for all missing data — no empty cells

---

## Supported Species

### Non-human Animals

| Chinese | English | Latin | NCBI Taxon |
|---------|---------|-------|------------|
| 马 | Horse | Equus caballus | 9796 |
| 鼠 / 小鼠 | Mouse | Mus musculus | 10090 |
| 大鼠 | Rat | Rattus norvegicus | 10116 |
| 犬 / 狗 | Dog | Canis lupus familiaris | 9615 |
| 猫 | Cat | Felis catus | 9685 |
| 兔 / 家兔 | Rabbit | Oryctolagus cuniculus | 9986 |
| 猪 | Pig | Sus scrofa domesticus | 9825 |
| 牛 / 奶牛 | Cattle | Bos taurus | 9913 |
| 绵羊 | Sheep | Ovis aries | 9940 |
| 山羊 | Goat | Capra hircus | 9925 |
| 斑马鱼 | Zebrafish | Danio rerio | 7955 |
| 豚鼠 | Guinea pig | Cavia porcellus | 10141 |
| 仓鼠 | Hamster | Mesocricetus auratus | 10036 |
| 鸡 | Chicken | Gallus gallus domesticus | 9031 |
| 猴 / 恒河猴 | Rhesus macaque | Macaca mulatta | 9544 |

> Missing a species? Edit `_SPECIES_DB` in `skill/species.py` and submit a PR.

---

## Configuration

Edit `config.yaml` before first use:

```yaml
search:
  max_results: 100
  timeout: 30
  email: "your-email@example.com"   # REQUIRED — NCBI Entrez requires this
  api_key: ""                       # Optional — get one at https://account.ncbi.nlm.nih.gov/

ena:
  base_url: "https://www.ebi.ac.uk/ena/browser/api"

export:
  default_format: "xlsx"
  output_dir: "./output"            # Directory for exported files
```

---

## Project Structure

```
skin_microbiome_skill/
├── README.md
├── LICENSE
├── config.yaml              # NCBI email, ENA URL, export settings
├── pyproject.toml
├── setup.py
├── requirements.txt
├── skill/                   # Core Python package
│   ├── __init__.py
│   ├── main.py              # Orchestrator + interactive CLI
│   ├── species.py           # Chinese/English → Latin name mapper
│   ├── search.py            # PubMed query + filter + site extraction
│   ├── ena.py               # BioProject resolver via ENA API
│   └── export.py            # Excel/CSV/JSON exporter (7 columns)
├── scripts/
│   ├── install.sh           # Linux/macOS Conda installer
│   └── install.ps1          # Windows Conda installer
└── tests/
    └── test_skill.py        # 30+ pytest cases with mock PubMed
```

---

## Running Tests

```bash
# Install dev dependencies
pip install pytest openpyxl biopython pyyaml

# Run all tests (mocked — no network required)
pytest tests/test_skill.py -v

# With coverage
pip install pytest-cov
pytest tests/test_skill.py --cov=skill --cov-report=term-missing
```

---

## API Reference

### `SkillMicrobiomeSkill` (main entry point)

| Method | Description |
|--------|-------------|
| `run_interactive()` | Full interactive session with prompts and preview |
| `run_pipeline(species, extra_keywords, max_results, export_format)` | Non-interactive one-shot pipeline |
| `search(species_latin, extra_keywords)` | PubMed search + filter only |
| `get_species_info(name)` | Normalize species name (Chinese/English → Latin) |
| `export(data, format, output_path)` | Export article list to file |

### `SpeciesManager`

| Method | Description |
|--------|-------------|
| `normalize(name)` | Chinese/English/Latin → canonical dict (`chinese`, `english`, `latin`, `taxon_id`) |
| `list_all()` | All species (animals + microbes) |
| `list_animals()` | Non-human animals only |
| `search(keyword)` | Fuzzy search across all name fields |

### `SearchEngine`

| Method | Description |
|--------|-------------|
| `search(species_latin, extra_keywords)` | Full PubMed pipeline: query → filter → site extraction |
| `extract_sampling_site(article)` | Extract anatomical site from abstract |
| `extract_bioproject_ids(article)` | Extract PRJNAxxx/PRJEBxxx IDs |
| `extract_ena_ids(article)` | Extract all ENA/SRA accessions |

---

## GitHub Repository

- **Repository**: [https://github.com/your-org/skin_microbiome_skill](https://github.com/your-org/skin_microbiome_skill)
- **Issues**: Bug reports and feature requests are welcome
- **Contributing**: Fork the repo, create a branch, and submit a pull request

### Adding a New Species

1. Edit `skill/species.py`
2. Add an entry to `_SPECIES_DB`:
   ```python
   {"chinese": "新物种", "english": "New Animal", "latin": "Animalis novus", "taxon_id": "12345"},
   ```
3. Run tests to verify: `pytest tests/test_skill.py -v`

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for full text.

You are free to use, modify, and distribute this software for academic, research, or commercial purposes. Attribution is appreciated but not required.

---

## References

- [PubMed / NCBI Entrez](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
- [ENA Browser API](https://www.ebi.ac.uk/ena/browser/api)
- [Biopython Documentation](https://biopython.org/docs/)
