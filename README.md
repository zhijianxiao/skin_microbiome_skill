# Skin Microbiome Skill · 皮肤微生物组文献检索工具

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)

**非人类皮肤微生物组文献检索与宏基因组数据集定位工具。**

输入一个物种名（中文或英文），自动检索 PubMed 中该动物宿主的皮肤微生物组研究文献，过滤掉人类研究，通过 NCBI ELink 跨数据库导航自动发现关联的宏基因组 BioProject 数据集，从摘要中提取取样部位，最终导出为格式化的 Excel 文件。

---

## 工作流程

```
用户输入                    NCBI Entrez                    ELink 跨库导航              输出
───────────              ───────────────               ────────────────          ──────────────
 物种名                                                        ┌─────────────────────────────┐
  ↓                      ┌──────────────┐                    │  文献标题                     │
 SpeciesManager          │ SearchEngine │    ELink           │  作者                         │
 ├─ 本地缓存匹配           │              │  PubMed→BioProject │  年份                         │
 └─ NCBI Taxonomy API    │ PubMed 查询   │─────PRJNAxxx─────→│  DOI                          │
  ↓                      │ 字段标签语法   │  PubMed→SRA       │  实验物种（拉丁名）             │
 拉丁学名                  │ NOT human    │─────SRRxxxxxx────→│  宏基因组数据集（PRJNA/PRJEB）   │
  ↓                      │ [mesh]        │                    │  取样部位                      │
 PubMed 检索式             │              │  ESummary         └─────────────────────────────┘
  ↓                      └──────────────┘  元数据解析                     Excel
 文献列表                                                           （自动筛选 + 冻结首行）
  ↓
 二次过滤（非人类 + 皮肤相关）
  ↓
 取样部位提取（40+ 正则模式）
```

### 核心技术栈

| 步骤 | 使用的 NCBI Entrez 工具 |
|------|------------------------|
| 物种标准化 | `esearch(db='taxonomy')` + `esummary` |
| 文献检索 | `esearch(db='pubmed')` 字段标签语法 |
| 文献获取 | `efetch(rettype='medline', retmode='xml')` |
| 跨库导航 | `elink(dbfrom='pubmed', db='bioproject')` |
| SRA 关联 | `elink(dbfrom='pubmed', db='sra')` |
| 元数据解析 | `esummary(db='bioproject')` |

---

## 安装

### 前置要求

- **Conda**（Miniconda 或 Anaconda）
- **Python ≥ 3.9**
- **NCBI 邮箱**（PubMed API 强制要求，[注册地址](https://www.ncbi.nlm.nih.gov/account/)）
- **NCBI API Key**（可选，将速率限制从 3 次/秒提升到 10 次/秒）

### Linux / macOS

```bash
# 1. 克隆仓库
git clone https://github.com/zhijianxiao/skin_microbiome_skill.git
cd skin_microbiome_skill

# 2. 运行安装脚本（创建 Conda 环境 + 安装依赖）
bash scripts/install.sh

# 3. 激活环境
conda activate skin_microbiome

# 4. 编辑 config.yaml，填入你的 NCBI 邮箱
#    将 user@example.com 替换为你的真实邮箱

# 5. 验证安装
skin-microbiome
```

### Windows (PowerShell)

```powershell
# 1. 克隆仓库
git clone https://github.com/zhijianxiao/skin_microbiome_skill.git
cd skin_microbiome_skill

# 2. 运行安装脚本
.\scripts\install.ps1

# 3. 激活环境
conda activate skin_microbiome

# 4. 编辑 config.yaml，填入你的 NCBI 邮箱

# 5. 验证安装
skin-microbiome
```

### 手动安装（不使用 Conda）

```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
# .\venv\Scripts\Activate.ps1   # Windows PowerShell

pip install -r requirements.txt
pip install -e .
```

---

## 快速开始

### 交互模式

```bash
$ skin-microbiome
```

```
============================================================
  Non-Human Skin Microbiome Literature Search
  Platform: linux
  Methods: NCBI Entrez + ELink
============================================================

  Species name (Chinese/English, e.g. 马 / mouse): 马

  Species: 马 → Horse → Equus caballus  (taxon=9796)

  Extra keywords (optional, Enter to skip):

  Searching PubMed (max 100)…
  Query: field-tagged, NOT human[mesh], ELink → BioProject / SRA
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

  Resolving BioProject metadata (ESummary pattern)…
  BioProjects found via ELink in 8/23 articles.

  Export format:
    [1] Excel (.xlsx) — default
    [2] CSV
    [3] JSON
    [4] Skip
  > 1

  Exported to: ./output/Equus_caballus_20260520_143022.xlsx
```

### 脚本调用（非交互式）

```python
from skill import SkinMicrobiomeSkill

skill = SkinMicrobiomeSkill(config_path="config.yaml")

# 一行完成：检索 + 过滤 + 导出
articles = skill.run_pipeline(
    species="鼠",
    extra_keywords="atopic dermatitis",
    max_results=50,
    export_format="xlsx",
)

# 查看结果
for art in articles:
    print(f"[{art['sampling_site']}] {art['title'][:60]}...")
```

### CLI 命令

```bash
# 列出所有支持的物种
skin-microbiome list-species

# 命令行检索
skin-microbiome search 马
skin-microbiome search mouse "atopic dermatitis"
```

---

## 输出格式

Excel 文件包含固定的 **7 列**：

| 列名 | 示例值 | 说明 |
|------|--------|------|
| 文献标题 | Characterization of the equine skin microbiome in healthy horses | PubMed 完整标题 |
| 作者 | Smith J; Brown A | 分号分隔，最多显示 10 人 |
| 年份 | 2025 | 出版年份 |
| DOI | 10.1111/vde.13001 | 无 DOI 时填 `N/A` |
| 实验物种 | Equus caballus | species.py 标准化后的拉丁学名 |
| 宏基因组数据集 | PRJNA123456; PRJEB998877 | 通过 ELink 自动发现的 BioProject ID，无则填 `N/A` |
| 取样部位 | Ear | 从摘要中提取的解剖部位，无法识别填 `N/A` |

输出 Excel 特性：
- **自动筛选** — 所有列支持排序和筛选
- **冻结首行** — 滚动时表头始终可见
- **标题列自动换行**
- **缺失值统一标记 `N/A`** — 无空白单元格

---

## 支持的物种

### 非人类动物（本地数据库）

| 中文名 | 英文名 | 拉丁学名 | NCBI Taxon ID |
|--------|--------|----------|---------------|
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

> **动态查找**：如果物种不在本地数据库中，Skill 会自动调用 NCBI Taxonomy API（`esearch` + `esummary`）进行在线查找。任何 NCBI 收录的物种都可以检索。

---

## 配置

首次使用前编辑 `config.yaml`：

```yaml
# PubMed / NCBI Entrez 设置
search:
  max_results: 100
  timeout: 30
  email: "your-email@example.com"   # 必填 — 替换为你的 NCBI 注册邮箱
  api_key: ""                       # 可选 — 在 https://account.ncbi.nlm.nih.gov/ 获取

# ENA 浏览器 API
ena:
  base_url: "https://www.ebi.ac.uk/ena/browser/api"

# 输出设置
export:
  default_format: "xlsx"
  output_dir: "./output"            # 导出文件存放目录
```

---

## 项目结构

```
skin_microbiome_skill/
├── README.md                   # 本文件
├── .gitignore
├── config.yaml                 # NCBI 邮箱、ENA URL、导出设置
├── pyproject.toml              # 现代 Python 项目元数据
├── setup.py                    # setuptools 打包配置
├── requirements.txt            # Python 依赖
├── skill/                      # 核心 Python 包
│   ├── __init__.py             # 包入口，v0.3.0
│   ├── main.py                 # 主控模块（交互 CLI + 脚本 API）
│   ├── species.py              # 物种名标准化（本地缓存 + NCBI Taxonomy API）
│   ├── search.py               # PubMed 检索（字段标签 + ELink 跨库导航）
│   ├── ena.py                  # BioProject / SRA 解析（ESummary + ELink）
│   └── export.py               # Excel/CSV/JSON 导出（7 列固定格式）
├── scripts/
│   ├── install.sh              # Linux/macOS Conda 安装脚本
│   └── install.ps1             # Windows Conda 安装脚本
└── tests/
    └── test_skill.py           # 30+ pytest 测试用例（mock NCBI）
```

---

## 运行测试

```bash
# 安装开发依赖
pip install pytest openpyxl biopython pyyaml

# 运行全部测试（mock 模式，无需网络）
pytest tests/test_skill.py -v

# 含覆盖率报告
pip install pytest-cov
pytest tests/test_skill.py --cov=skill --cov-report=term-missing
```

---

## API 参考

### `SkinMicrobiomeSkill`（主入口）

| 方法 | 说明 |
|------|------|
| `run_interactive()` | 完整交互式会话（含预览和关键词优化） |
| `run_pipeline(species, extra_keywords, max_results, export_format)` | 非交互式一键管线 |
| `search(species_latin, extra_keywords)` | 仅执行 PubMed 检索 + 过滤 |
| `get_species_info(name)` | 物种名标准化（中文/英文 → 拉丁学名） |
| `export(data, format, output_path)` | 导出文献列表到文件 |

### `SpeciesManager`

| 方法 | 说明 |
|------|------|
| `normalize(name)` | 中文/英文/拉丁名 → 标准化字典（`chinese`, `english`, `latin`, `taxon_id`） |
| `list_all()` | 列出本地数据库中所有物种 |
| `list_animals()` | 仅列出非人类动物 |
| `search(keyword)` | 跨字段模糊搜索 |
| `_ncbi_taxonomy_lookup(name)` | NCBI Taxonomy API 动态查找（不在本地库中的物种） |

### `SearchEngine`

| 方法 | 说明 |
|------|------|
| `search(species_latin, extra_keywords)` | 完整检索管线：查询 → 过滤 → ELink → 部位提取 |
| `_elink_pubmed_to_bioproject(pmids)` | ELink PubMed → BioProject 批量跨库导航 |
| `_elink_pubmed_to_sra(pmids)` | ELink PubMed → SRA 批量跨库导航 |
| `extract_sampling_site(article)` | 从摘要中提取解剖取样部位 |
| `extract_bioproject_ids(article)` | 正则提取 BioProject ID（回退方案） |

### `ENAClient`

| 方法 | 说明 |
|------|------|
| `resolve_bioproject(bioproject_id)` | 通过 ESummary 获取 BioProject 标题/描述 |
| `get_bioproject_summary(bioproject_id)` | 获取完整 BioProject 元数据 |
| `get_sra_runs_for_bioproject(bioproject_id)` | ELink BioProject → SRA 运行列表 |

---

## GitHub 仓库

- **仓库地址**：[https://github.com/zhijianxiao/skin_microbiome_skill](https://github.com/zhijianxiao/skin_microbiome_skill)
- **问题反馈**：欢迎提交 Bug 报告和功能建议
- **贡献指南**：Fork → 创建分支 → 提交 PR

### 添加新物种

1. 编辑 `skill/species.py`
2. 在 `_LOCAL_DB` 字典中添加条目：
   ```python
   "新物种中文名": {"chinese": "...", "english": "...", "latin": "...", "taxon_id": "..."},
   ```
3. 运行测试验证：`pytest tests/test_skill.py -v`
