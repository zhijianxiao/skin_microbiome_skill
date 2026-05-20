"""Tests for skin_microbiome_skill — non-human skin microbiome pipeline."""

import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from skill import (
    SkinMicrobiomeSkill,
    SpeciesManager,
    SearchEngine,
    ENAClient,
    Exporter,
    detect_platform,
)

# ═══════════════════════════════════════════════════════════════════════
# Fake PubMed data for Entrez mock
# ═══════════════════════════════════════════════════════════════════════

_FAKE_PUBMED = {
    "PubmedArticle": [
        {  # Article 1: Horse skin microbiome — should PASS filters
            "MedlineCitation": {
                "PMID": "40000001",
                "Article": {
                    "ArticleTitle": "Characterization of the equine skin microbiome in healthy horses",
                    "AuthorList": [
                        {"LastName": "Smith", "ForeName": "John"},
                        {"LastName": "Brown", "ForeName": "Alice"},
                    ],
                    "Journal": {
                        "Title": "Veterinary Dermatology",
                        "JournalIssue": {"PubDate": {"Year": "2025"}},
                    },
                    "ELocationID": [
                        {"EIdType": "doi", "value": "10.1111/vde.13001"},
                    ],
                    "Abstract": {
                        "AbstractText": [
                            "We collected skin swabs from the ear, axilla, and groin",
                            "of 20 healthy horses. Metagenomic sequencing (PRJNA123456)",
                            "revealed diverse bacterial communities.",
                        ]
                    },
                },
            }
        },
        {  # Article 2: Mouse skin — should PASS filters
            "MedlineCitation": {
                "PMID": "40000002",
                "Article": {
                    "ArticleTitle": "Skin microbiota of laboratory mice",
                    "AuthorList": [
                        {"LastName": "Lee", "ForeName": "Sarah"},
                    ],
                    "Journal": {
                        "Title": "Lab Animal",
                        "JournalIssue": {"PubDate": {"Year": "2024"}},
                    },
                    "ELocationID": [
                        {"EIdType": "doi", "value": "10.1038/laban.2024.001"},
                    ],
                    "Abstract": {
                        "AbstractText": [
                            "We characterized the dorsal and ventral skin microbiome",
                            "of C57BL/6 mice using 16S rRNA sequencing.",
                        ]
                    },
                },
            }
        },
        {  # Article 3: HUMAN skin — should be EXCLUDED by secondary filter
            "MedlineCitation": {
                "PMID": "40000003",
                "Article": {
                    "ArticleTitle": "Human skin microbiome in patients with atopic dermatitis",
                    "AuthorList": [
                        {"LastName": "Kim", "ForeName": "Daniel"},
                    ],
                    "Journal": {
                        "Title": "J Invest Dermatol",
                        "JournalIssue": {"PubDate": {"Year": "2023"}},
                    },
                    "ELocationID": [
                        {"EIdType": "doi", "value": "10.1016/jid.2023.01.001"},
                    ],
                    "Abstract": {
                        "AbstractText": [
                            "We enrolled 50 human patients with atopic dermatitis...",
                        ]
                    },
                },
            }
        },
        {  # Article 4: Gut microbiome (not skin) — should be EXCLUDED
            "MedlineCitation": {
                "PMID": "40000004",
                "Article": {
                    "ArticleTitle": "Gut microbiota of horses fed different diets",
                    "AuthorList": [
                        {"LastName": "Jones", "ForeName": "Mike"},
                    ],
                    "Journal": {
                        "Title": "Equine Vet J",
                        "JournalIssue": {"PubDate": {"Year": "2022"}},
                    },
                    "Abstract": {
                        "AbstractText": [
                            "We analyzed fecal samples from 30 horses...",
                        ]
                    },
                },
            }
        },
        {  # Article 5: Dog skin — should PASS filters
            "MedlineCitation": {
                "PMID": "40000005",
                "Article": {
                    "ArticleTitle": "The cutaneous microbiome of dogs with allergic dermatitis",
                    "AuthorList": [
                        {"LastName": "Park", "ForeName": "Eve"},
                        {"LastName": "Wilson", "ForeName": "Tom"},
                    ],
                    "Journal": {
                        "Title": "Vet Dermatol",
                        "JournalIssue": {"PubDate": {"Year": "2025"}},
                    },
                    "Abstract": {
                        "AbstractText": [
                            "Skin swabs from the paw and interdigital spaces of",
                            "atopic dogs were sequenced (PRJEB998877).",
                        ]
                    },
                },
            }
        },
    ]
}


def _entrez_read_mock(handle):
    """Simulate Entrez.read — esearch returns ID list, efetch returns articles."""
    name = str(getattr(handle, "name", ""))
    if "esearch" in name:
        return {"IdList": ["40000001", "40000002", "40000003", "40000004", "40000005"]}
    return _FAKE_PUBMED


@pytest.fixture
def entrez_mock():
    """Patch all Bio.Entrez calls to return fake PubMed data."""
    with patch("Bio.Entrez.esearch") as m_es, \
         patch("Bio.Entrez.efetch") as m_ef, \
         patch("Bio.Entrez.read", side_effect=_entrez_read_mock):
        m_es.return_value = MagicMock()
        m_es.return_value.read.return_value = ""
        m_ef.return_value = MagicMock()
        m_ef.return_value.read.return_value = ""
        yield


@pytest.fixture
def search_engine():
    return SearchEngine({
        "search": {"max_results": 100, "timeout": 30, "email": "test@test.com"},
    })


@pytest.fixture
def species_manager():
    return SpeciesManager()


@pytest.fixture
def exporter():
    return Exporter({"export": {"default_format": "xlsx", "output_dir": "./output"}})


@pytest.fixture
def sample_articles():
    return [
        {
            "pmid": "10001",
            "title": "Equine skin microbiome diversity",
            "authors": "Alice Chen; Bob Li",
            "year": "2024",
            "doi": "10.1000/equine.2024.001",
            "abstract": "Skin swabs from horse ear and back...",
            "species": "Equus caballus",
            "bioproject_ids": ["PRJNA123456"],
            "sampling_site": "Ear",
        },
        {
            "pmid": "10002",
            "title": "Mouse dorsal skin microbiota changes with age",
            "authors": "Charlie Wang",
            "year": "2023",
            "doi": "",
            "abstract": "Dorsal skin of C57BL/6 mice...",
            "species": "Mus musculus",
            "bioproject_ids": [],
            "sampling_site": "Back",
        },
        {
            "pmid": "10003",
            "title": "Canine cutaneous fungal communities",
            "authors": "Diana Park; Eve Kim",
            "year": "2025",
            "doi": "10.1000/canine.2025.003",
            "abstract": "Paw skin microbiome of dogs...",
            "species": "Canis lupus familiaris",
            "bioproject_ids": ["PRJEB998877"],
            "sampling_site": "Paw",
        },
    ]


# ═══════════════════════════════════════════════════════════════════════
# 1. Species normalization
# ═══════════════════════════════════════════════════════════════════════

class TestSpeciesNormalization:

    def test_ma_normalizes_to_equus_caballus(self, species_manager):
        result = species_manager.normalize("马")
        assert result is not None
        assert result["latin"] == "Equus caballus"
        assert result["english"] == "Horse"
        assert result["chinese"] == "马"
        assert result["taxon_id"] == "9796"

    def test_shu_normalizes_to_mus_musculus(self, species_manager):
        """输入 '鼠' 应返回 Mus musculus."""
        result = species_manager.normalize("鼠")
        assert result is not None
        assert result["latin"] == "Mus musculus"
        assert result["english"] == "Mouse"

    def test_xiaoshu_normalizes_to_mus_musculus(self, species_manager):
        """输入 '小鼠' 也应返回 Mus musculus."""
        result = species_manager.normalize("小鼠")
        assert result is not None
        assert result["latin"] == "Mus musculus"

    def test_english_mouse(self, species_manager):
        result = species_manager.normalize("mouse")
        assert result is not None
        assert result["latin"] == "Mus musculus"

    def test_latin_input(self, species_manager):
        result = species_manager.normalize("Equus caballus")
        assert result is not None
        assert result["chinese"] == "马"

    def test_case_insensitive(self, species_manager):
        result = species_manager.normalize("MUS MUSCULUS")
        assert result is not None
        assert result["latin"] == "Mus musculus"

    def test_unknown_returns_none(self, species_manager):
        assert species_manager.normalize("外星生物XYZ") is None

    def test_list_animals(self, species_manager):
        animals = species_manager.list_animals()
        latins = [a["latin"] for a in animals]
        assert "Equus caballus" in latins
        assert "Mus musculus" in latins
        # Microbes excluded
        assert "Staphylococcus epidermidis" not in latins

    def test_list_all_includes_both(self, species_manager):
        all_s = species_manager.list_all()
        latins = [s["latin"] for s in all_s]
        assert "Equus caballus" in latins
        assert "Staphylococcus epidermidis" in latins

    def test_search_by_keyword(self, species_manager):
        results = species_manager.search("马")
        assert len(results) >= 1
        assert any(r["latin"] == "Equus caballus" for r in results)

    def test_get_info(self, species_manager):
        info = species_manager.get_info("狗")
        assert info["latin"] == "Canis lupus familiaris"

    def test_get_info_unknown(self, species_manager):
        info = species_manager.get_info("火星细菌")
        assert "error" in info


# ═══════════════════════════════════════════════════════════════════════
# 2. Search: non-human skin microbiome query + filter
# ═══════════════════════════════════════════════════════════════════════

class TestSearchEngine:

    def test_search_returns_articles(self, entrez_mock, search_engine):
        """PubMed search should return articles passing non-human skin filter."""
        articles = search_engine.search(species_latin="Equus caballus")
        assert isinstance(articles, list)
        assert len(articles) >= 1
        for art in articles:
            assert "title" in art
            assert "sampling_site" in art
            assert "bioproject_ids" in art

    def test_human_patients_excluded(self, entrez_mock, search_engine):
        """Article 3 mentions 'human patients' — must be excluded."""
        articles = search_engine.search(species_latin="Equus caballus")
        pmids = [a["pmid"] for a in articles]
        assert "40000003" not in pmids, "Human patient article should be excluded!"

    def test_non_skin_excluded(self, entrez_mock, search_engine):
        """Article 4 is about gut microbiota, not skin — must be excluded."""
        articles = search_engine.search(species_latin="Equus caballus")
        pmids = [a["pmid"] for a in articles]
        assert "40000004" not in pmids, "Gut microbiota article should be excluded!"

    def test_skin_articles_present(self, entrez_mock, search_engine):
        """Articles 1 (horse skin) and 5 (dog skin) should pass filters."""
        articles = search_engine.search(species_latin="Equus caballus")
        pmids = [a["pmid"] for a in articles]
        assert "40000001" in pmids, "Horse skin article should be included"
        assert "40000005" in pmids, "Dog skin article should be included"

    def test_sampling_site_extraction(self, entrez_mock, search_engine):
        """Article 1 mentions ear, axilla, groin — should extract a site."""
        articles = search_engine.search(species_latin="Equus caballus")
        art1 = next((a for a in articles if a["pmid"] == "40000001"), None)
        assert art1 is not None
        assert art1["sampling_site"] != "N/A", f"Should find sampling site, got {art1['sampling_site']}"
        assert art1["sampling_site"] in ("Ear", "Axilla", "Groin")

    def test_sampling_site_n_a(self, entrez_mock, search_engine):
        """Article 2 has 'dorsal and ventral skin' — dorsal→Back. Should not be N/A."""
        articles = search_engine.search(species_latin="Mus musculus")
        art2 = next((a for a in articles if a["pmid"] == "40000002"), None)
        assert art2 is not None
        # "dorsal" maps to "Back", "ventral" maps to "Abdomen"
        assert art2["sampling_site"] != "N/A"

    def test_bioproject_extraction(self, entrez_mock, search_engine):
        """Article 1 has PRJNA123456 in abstract."""
        articles = search_engine.search(species_latin="Equus caballus")
        art1 = next((a for a in articles if a["pmid"] == "40000001"), None)
        assert art1 is not None
        assert "PRJNA123456" in art1["bioproject_ids"]

    def test_bioproject_empty(self, entrez_mock, search_engine):
        """Article 2 has no BioProject ID."""
        articles = search_engine.search(species_latin="Mus musculus")
        art2 = next((a for a in articles if a["pmid"] == "40000002"), None)
        assert art2 is not None
        assert art2["bioproject_ids"] == []

    def test_extract_ena_ids_all(self, search_engine):
        """General ENA ID extraction catches SRR/ERR/SAMN etc."""
        ids = search_engine.extract_ena_ids({
            "title": "Study with SRR1111111, ERR2222222, SAMN3333333",
            "abstract": "Also PRJNA444444.",
        })
        assert "SRR1111111" in ids
        assert "ERR2222222" in ids
        assert "SAMN3333333" in ids
        assert "PRJNA444444" in ids

    def test_extract_bioproject_only_bioprojects(self, search_engine):
        """extract_bioproject_ids should ONLY return PRJNA/PRJEB/PRJDB."""
        ids = search_engine.extract_bioproject_ids({
            "title": "SRR11111 and PRJNA22222 and ERR33333",
            "abstract": "PRJEB44444 too.",
        })
        assert ids == ["PRJEB44444", "PRJNA22222"]
        assert "SRR11111" not in ids
        assert "ERR33333" not in ids

    def test_empty_search(self, entrez_mock, search_engine):
        articles = search_engine.search(species_latin="")
        assert isinstance(articles, list)


# ═══════════════════════════════════════════════════════════════════════
# 3. Export: fixed 7 columns, N/A for missing
# ═══════════════════════════════════════════════════════════════════════

_EXPECTED_HEADERS = ["文献标题", "作者", "年份", "DOI", "实验物种", "宏基因组数据集", "取样部位"]


class TestExporter:

    def test_columns_are_exactly_7(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "test.xlsx")
            exporter.to_excel(sample_articles, fp)
            from openpyxl import load_workbook
            wb = load_workbook(fp)
            ws = wb.active
            headers = [ws.cell(row=1, column=c).value for c in range(1, 9)]
            assert headers == _EXPECTED_HEADERS
            # Column 8 should not exist (only 7 columns)
            assert ws.cell(row=1, column=8).value is None
            wb.close()

    def test_missing_doi_is_n_a(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "test.xlsx")
            exporter.to_excel(sample_articles, fp)
            from openpyxl import load_workbook
            wb = load_workbook(fp)
            ws = wb.active
            # Article 2 has empty DOI
            row3_doi = ws.cell(row=3, column=4).value
            assert row3_doi == "N/A", f"Empty DOI should be N/A, got: {row3_doi}"
            wb.close()

    def test_missing_bioproject_is_n_a(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "test.xlsx")
            exporter.to_excel(sample_articles, fp)
            from openpyxl import load_workbook
            wb = load_workbook(fp)
            ws = wb.active
            # Article 2 has empty bioproject_ids
            row3_bp = ws.cell(row=3, column=6).value
            assert row3_bp == "N/A", f"Empty bioproject should be N/A, got: {row3_bp}"
            wb.close()

    def test_all_rows_present(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "test.xlsx")
            exporter.to_excel(sample_articles, fp)
            from openpyxl import load_workbook
            wb = load_workbook(fp)
            ws = wb.active
            # 3 data rows + 1 header
            assert ws.max_row == 4
            # All cells in data rows should be non-None
            for row in range(2, 5):
                for col in range(1, 8):
                    val = ws.cell(row=row, column=col).value
                    assert val is not None, f"Empty cell at row={row}, col={col}"
            wb.close()

    def test_csv_export(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "test.csv")
            exporter.to_csv(sample_articles, fp)
            content = Path(fp).read_text(encoding="utf-8-sig")
            for h in _EXPECTED_HEADERS:
                assert h in content
            assert "N/A" in content

    def test_json_export(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "test.json")
            exporter.to_json(sample_articles, fp)
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == 3

    def test_empty_list_export(self, exporter):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "empty.xlsx")
            exporter.to_excel([], fp)
            assert os.path.getsize(fp) > 0

    def test_auto_filename(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter.output_dir = Path(tmpdir)
            result = exporter.export(sample_articles, format="xlsx", species_name="Equus_caballus")
            assert result is not None
            assert os.path.isfile(result)
            assert "Equus_caballus" in str(result)

    def test_excel_has_autofilter(self, exporter, sample_articles):
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "filtered.xlsx")
            exporter.to_excel(sample_articles, fp)
            from openpyxl import load_workbook
            wb = load_workbook(fp)
            ws = wb.active
            assert ws.auto_filter.ref is not None, "Auto-filter should be set"
            wb.close()


# ═══════════════════════════════════════════════════════════════════════
# 4. ENA module
# ═══════════════════════════════════════════════════════════════════════

class TestENAClient:

    def test_resolve_bioproject_n_a_when_no_data(self):
        client = ENAClient()
        with patch("skill.ena._ena_get", return_value=None):
            result = client.resolve_bioproject("PRJNA000000")
            assert result == "N/A"

    def test_resolve_bioproject_returns_title(self):
        client = ENAClient()
        fake_data = {"title": "Equine skin metagenome", "description": "Raw reads"}
        with patch("skill.ena._ena_get", return_value=fake_data):
            result = client.resolve_bioproject("PRJNA123456")
            assert result == "Equine skin metagenome"

    def test_get_bioproject_summary_n_a(self):
        client = ENAClient()
        with patch("skill.ena._ena_get", return_value=None):
            result = client.get_bioproject_summary("PRJNA000000")
            assert result == {"error": "N/A"}


# ═══════════════════════════════════════════════════════════════════════
# 5. Integration
# ═══════════════════════════════════════════════════════════════════════

class TestSkinMicrobiomeSkillIntegration:

    def test_init_loads_modules(self):
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        assert skill.species_manager is not None
        assert skill.search_engine is not None
        assert skill.ena_client is not None
        assert skill.exporter is not None

    def test_get_species_info(self):
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        info = skill.get_species_info("马")
        assert info["latin"] == "Equus caballus"

    def test_get_species_info_mouse(self):
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        info = skill.get_species_info("鼠")
        assert info["latin"] == "Mus musculus"

    def test_search_delegates(self, entrez_mock):
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        results = skill.search(species_latin="Equus caballus")
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_detect_platform(self):
        plat = detect_platform()
        assert plat in ("linux", "windows", "macos")

    def test_export_integration(self, sample_articles):
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        with tempfile.TemporaryDirectory() as tmpdir:
            fp = os.path.join(tmpdir, "integration.xlsx")
            result = skill.export(sample_articles, format="xlsx", output_path=fp)
            assert result == fp
            assert os.path.isfile(fp)
            assert os.path.getsize(fp) > 0

    def test_run_pipeline(self, entrez_mock):
        """Non-interactive pipeline should work end-to-end."""
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        with tempfile.TemporaryDirectory() as tmpdir:
            skill.exporter.output_dir = Path(tmpdir)
            articles = skill.run_pipeline(
                species="马",
                extra_keywords="dermatitis",
                max_results=20,
                export_format="xlsx",
            )
            assert isinstance(articles, list)
            assert len(articles) >= 1
            for art in articles:
                assert art["species"] == "Equus caballus"
                assert "sampling_site" in art
                assert "bioproject_ids" in art

    def test_unknown_species_raises(self):
        skill = SkinMicrobiomeSkill(config_path="config.yaml")
        with pytest.raises(ValueError, match="Unknown species"):
            skill.run_pipeline(species="不存在的物种XYZ")

    def test_version(self):
        from skill import __version__
        assert __version__ == "0.2.0"
