# skinmicrobiome · 皮肤微生物组文献检索工具

**非人类皮肤微生物组文献检索与宏基因组数据集定位工具。**

输入一个物种名（中文/英文/拉丁名），自动检索 PubMed 中该宿主的皮肤微生物组研究，过滤人类研究，通过 NCBI ELink 跨库导航发现关联的宏基因组（BioProject / SRA）数据集，从摘要中提取取样部位，按相关性评分排序，最终导出为格式化 Excel 文件。

---

## 安装

### 前置要求

- **Conda**（Miniconda 或 Anaconda）
- **Python ≥ 3.9**
- **NCBI 邮箱**（PubMed API 强制要求，[注册地址](https://www.ncbi.nlm.nih.gov/account/)）
- **NCBI API Key**（可选，将速率限制从 3 次/秒提升到 10 次/秒，[获取地址](https://account.ncbi.nlm.nih.gov/)）

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
skinmicrobiome
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
skinmicrobiome
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
$ skinmicrobiome
```

```
============================================================
  Non-Human Skin Microbiome Literature Search
  Platform: linux
  Methods: NCBI Entrez + ELink
============================================================

  Species name (Chinese/English, e.g. 马 / mouse): 马

  Species: 马 → Horse → Equus caballus  (taxon=9796)

  Expanding search terms (NCBI Taxonomy)…
  Boolean terms (5): Equus caballus, Equus, horse, domestic horse, equid

  Extra keywords (optional, Enter to skip):

  Searching PubMed (max 100)…
  Query: Boolean keyword, NOT human
  → 23 articles after non-human skin filter + scoring.

────────────────────────────────────────────────────────────
  Preview — top 10 of 23 (sorted by relevance score)
────────────────────────────────────────────────────────────
  [ 1] [18.5] Characterization of the equine skin microbiome in healthy horses
       year=2025  site=Ear  bioproject=PRJNA123456
  [ 2] [15.2] Cutaneous fungal diversity in thoroughbred horses
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
skinmicrobiome list-species          # 列出所有支持的物种
skinmicrobiome search 马             # 命令行检索
skinmicrobiome search mouse "atopic dermatitis"
```

---

## 输出格式

Excel 文件固定 **7 列**：`文献标题` | `作者` | `年份` | `DOI` | `实验物种` | `宏基因组数据集` | `取样部位`

- **自动筛选 + 冻结首行** — 所有列可排序和筛选，表头始终可见
- **缺失值统一标记 `N/A`** — 无空白单元格
- **按相关性评分降序排列**

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

> **动态查找**：如果物种不在本地数据库中，skill 会自动调用 NCBI Taxonomy API 进行在线查找。任何 NCBI 收录的物种都可以检索。

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
├── config.yaml              # NCBI 邮箱、ENA URL、导出设置
├── pyproject.toml           # 项目元数据
├── setup.py                 # setuptools 打包
├── requirements.txt         # Python 依赖
├── skill/                   # 核心 Python 包
│   ├── main.py              # 主控模块（交互 CLI + 脚本 API）
│   ├── species.py           # 物种标准化（本地缓存 + NCBI Taxonomy）
│   ├── search.py            # PubMed 检索（字段标签 + ELink）
│   ├── ena.py               # BioProject / SRA 解析
│   └── export.py            # Excel/CSV/JSON 导出
├── scripts/
│   ├── install.sh           # Linux/macOS 安装
│   └── install.ps1          # Windows 安装
└── tests/
    └── test_skill.py        # pytest 测试（mock NCBI）
```

---

## 运行测试

```bash
pip install pytest pytest-cov
pytest tests/test_skill.py -v
pytest tests/test_skill.py --cov=skill --cov-report=term-missing
```

---

## API 参考

**`SkinMicrobiomeSkill`** — 主入口：`run_interactive()` | `run_pipeline()` | `search()` | `get_species_info()` | `export()`

**`SpeciesManager`** — 物种标准化：`normalize()` | `list_all()` | `list_animals()` | `_ncbi_taxonomy_lookup()`

**`SearchEngine`** — 文献检索：`search()` | `_elink_pubmed_to_bioproject()` | `extract_sampling_site()`

**`ENAClient`** — 数据解析：`resolve_bioproject()` | `get_bioproject_summary()` | `get_sra_runs_for_bioproject()`

---

## 链接

- **仓库**：[github.com/zhijianxiao/skin_microbiome_skill](https://github.com/zhijianxiao/skin_microbiome_skill)
- **问题反馈**：欢迎提交 Issue 和 PR
