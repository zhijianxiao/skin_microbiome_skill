"""PubMed search for non-human skin microbiome with Boolean keyword query + relevance scoring.

Query structure:
  (species_terms...) AND (skin OR dermal OR cutaneous OR epidermal)
  AND (microbiome OR microbiota OR "microbial community") NOT human

Relevance scoring:
  +1.0  species name in title/abstract
  +0.5  skin-related terms in title/abstract
  +0.5  microbiome-related terms in title/abstract
"""

import re
import time

from Bio import Entrez
from Bio.Entrez import HTTPError

# ── Term sets ──────────────────────────────────────────────────────────
_SKIN_TERMS = [
    "skin", "cutaneous", "dermal", "dermis", "epidermal", "epidermis",
    "dermatitis", "dermatology", "dermatological", "eczema", "atopic",
    "seborrheic", "sebaceous", "keratinocyte", "melanocyte",
]

_MICROBIOME_TERMS = [
    "microbiome", "microbiota", "microbial community", "microbial communities",
    "bacterial community", "bacterial communities", "fungal community",
    "fungal communities", "mycobiome", "virome", "metagenomic",
]

_HUMAN_EXCLUSIVE = [
    "patient", "patients", "volunteer", "volunteers", "human subject",
    "clinical trial", "healthy adult", "healthy adults",
]

_SAMPLING_SITE_PATTERNS = [
    (r"\b(ear|ears|auricular|otic)\b", "Ear"),
    (r"\b(nose|nasal|nares|nostril)\b", "Nose"),
    (r"\b(cheek|cheeks|buccal|malar)\b", "Cheek"),
    (r"\b(forehead|frontal)\b", "Forehead"),
    (r"\b(scalp|scalps)\b", "Scalp"),
    (r"\b(axilla|axillae|armpit|axillary)\b", "Axilla"),
    (r"\b(neck|cervical|nape)\b", "Neck"),
    (r"\b(shoulder|shoulders|deltoid)\b", "Shoulder"),
    (r"\b(back|dorsal trunk|interscapular)\b", "Back"),
    (r"\b(chest|thoracic|sternal|pectoral)\b", "Chest"),
    (r"\b(abdomen|abdominal|belly|ventral)\b", "Abdomen"),
    (r"\b(groin|inguinal)\b", "Groin"),
    (r"\b(perineum|perineal|perianal|anal)\b", "Perineum"),
    (r"\b(forearm|volar forearm|antecubital)\b", "Forearm"),
    (r"\b(upper arm|brachial)\b", "Upper arm"),
    (r"\b(hand|hands|palmar|interdigital)\b", "Hand"),
    (r"\b(thigh|thighs|femoral)\b", "Thigh"),
    (r"\b(calf|calves|sural|lower leg|popliteal)\b", "Calf"),
    (r"\b(foot|feet|plantar|toe|toes)\b", "Foot"),
    (r"\b(paw|paws|footpad|footpads)\b", "Paw"),
    (r"\b(tail|tail base|rump)\b", "Tail"),
    (r"\b(fin|fins|dorsal fin|pectoral fin|pelvic fin|caudal fin)\b", "Fin"),
    (r"\b(gill|gills|branchial|opercular|operculum)\b", "Gill"),
    (r"\b(scale|scales|dermal denticle|denticles|placoid)\b", "Scale"),
    (r"\b(snout|rostrum|rostral)\b", "Snout"),
    (r"\b(mouth|oral|buccal|jaw|jaws|mandibular)\b", "Mouth"),
    (r"\b(clasper|claspers)\b", "Clasper"),
]


# ── PubMed record parser ───────────────────────────────────────────────
def _parse_medline(record: dict) -> dict:
    art = {}
    try:
        medline = record.get("MedlineCitation", record)
        a = medline.get("Article", {})
        art["pmid"] = str(medline.get("PMID", ""))
        art["title"] = a.get("ArticleTitle", "")

        authors = a.get("AuthorList", [])
        if isinstance(authors, list):
            names = []
            for au in authors:
                ln, fn = au.get("LastName", ""), au.get("ForeName", "")
                if ln:
                    names.append(f"{ln} {fn}".strip())
            art["authors"] = "; ".join(names[:10])
            if len(names) > 10:
                art["authors"] += " et al."
        else:
            art["authors"] = ""

        journal = a.get("Journal", {})
        art["journal"] = journal.get("Title", "")
        di = journal.get("JournalIssue", {}).get("PubDate", {})
        art["year"] = str(di.get("Year") or di.get("MedlineDate", ""))

        art["doi"] = ""
        eid = a.get("ELocationID", [])
        if isinstance(eid, dict):
            eid = [eid]
        for e in (eid or []):
            if isinstance(e, dict) and e.get("EIdType") == "doi":
                art["doi"] = str(e.get("value", e))
                break

        ap = a.get("Abstract", {}).get("AbstractText", [])
        if isinstance(ap, str):
            art["abstract"] = ap
        elif isinstance(ap, list):
            art["abstract"] = " ".join(str(p) for p in ap)
        else:
            art["abstract"] = ""
    except Exception:
        pass
    return art


# ═══════════════════════════════════════════════════════════════════════
class SearchEngine:
    """PubMed search with Boolean keyword query + relevance scoring.

    Query: (species_terms) AND (skin_terms) AND (microbiome_terms) NOT human

    Score: species_match * 1.0 + skin_match * 0.5 + microbiome_match * 0.5
    """

    def __init__(self, config: dict):
        self.config = config
        sc = config.get("search", {})
        self.max_results = sc.get("max_results", 100)
        self.timeout = sc.get("timeout", 30)
        self.email = sc.get("email", "user@example.com")
        self.api_key = sc.get("api_key", "")
        Entrez.email = self.email
        if self.api_key:
            Entrez.api_key = self.api_key

    # ── public API ─────────────────────────────────────────────────────
    def search(
        self,
        species_terms: dict,
        extra_keywords: str = "",
        max_results: int = None,
    ) -> list[dict]:
        """Search PubMed for non-human skin microbiome.

        Args:
          species_terms: dict from SpeciesManager.expand_search_terms()
                         must contain 'boolean_clause' and 'all' keys.
          extra_keywords: optional extra search terms
          max_results: override configured max results

        Returns list of article dicts sorted by relevance_score descending.
        """
        max_n = max_results or self.max_results

        # 1) Build Boolean keyword query
        query = self._build_query(species_terms, extra_keywords)

        # 2) ESearch
        pmids = self._esearch(query, max_n)
        if not pmids:
            return []

        # 3) EFetch
        articles = self._efetch(pmids)

        # 4) Secondary filter (non-human, skin-related)
        articles = self._filter_non_human_skin(articles)

        # 5) Score each article
        search_terms = species_terms.get("all", [])
        for art in articles:
            art["relevance_score"] = round(
                self._score_article(art, search_terms), 1
            )

        # 6) Sort by score descending
        articles.sort(key=lambda a: a.get("relevance_score", 0), reverse=True)

        # 7) Extract sampling sites
        for art in articles:
            art["sampling_site"] = self.extract_sampling_site(art)

        # 8) BioProject: regex extraction (does not depend on taxon_id)
        for art in articles:
            art["bioproject_ids"] = self.extract_bioproject_ids(art)

        return articles

    # ── query builder ──────────────────────────────────────────────────
    def _build_query(self, species_terms: dict, extra_keywords: str = "") -> str:
        """Build Boolean keyword PubMed query.

        Result pattern:
          (species_clause) AND (skin OR dermal OR ...)
          AND (microbiome OR microbiota OR ...) NOT human
        """
        species_clause = species_terms.get("boolean_clause", "")

        skin_clause = (
            "(skin OR dermal OR cutaneous OR epidermal OR dermatitis)"
        )
        micro_clause = (
            '(microbiome OR microbiota OR "microbial community"'
            ' OR "microbial communities" OR metagenomic)'
        )
        query = f"{species_clause} AND {skin_clause} AND {micro_clause} NOT human"

        if extra_keywords:
            query = f"({query}) AND ({extra_keywords})"

        return query

    # ── relevance scoring ──────────────────────────────────────────────
    def _score_article(self, article: dict, species_terms: list[str]) -> float:
        """Score an article by keyword presence in title + abstract.

        Scoring rules:
          +1.0  per species term match in title,  +0.3 in abstract
          +0.5  per skin term match in title,     +0.2 in abstract
          +0.5  per microbiome term match in title, +0.2 in abstract
        """
        title = (article.get("title") or "").lower()
        abstract = (article.get("abstract") or "").lower()

        score = 0.0

        # Species terms (genera, common names, scientific names)
        for term in species_terms:
            t = term.lower()
            if t in title:
                score += 1.0
            if t in abstract:
                score += 0.3

        # Skin terms
        for term in _SKIN_TERMS:
            if term in title:
                score += 0.5
            if term in abstract:
                score += 0.2

        # Microbiome terms
        for term in _MICROBIOME_TERMS:
            if term in title:
                score += 0.5
            if term in abstract:
                score += 0.2

        return min(score, 100.0)

    # ── ESearch / EFetch ───────────────────────────────────────────────
    def _esearch(self, query: str, max_n: int) -> list[str]:
        try:
            handle = Entrez.esearch(
                db="pubmed", term=query, retmax=max_n, retmode="json",
            )
            result = Entrez.read(handle)
            handle.close()
            return result.get("IdList", [])
        except HTTPError as e:
            print(f"[WARN] PubMed ESearch failed: {e}")
            return []

    def _efetch(self, pmids: list[str]) -> list[dict]:
        if not pmids:
            return []
        articles = []
        for i in range(0, len(pmids), 50):
            batch = pmids[i : i + 50]
            try:
                handle = Entrez.efetch(
                    db="pubmed", id=",".join(batch),
                    rettype="medline", retmode="xml",
                )
                records = Entrez.read(handle)
                handle.close()
                for rec in records.get("PubmedArticle", []):
                    articles.append(_parse_medline(rec))
            except HTTPError as e:
                print(f"[WARN] PubMed EFetch failed: {e}")
            time.sleep(0.34)
        return articles

    # ── ELink: PubMed → BioProject ─────────────────────────────────────
    def _elink_pubmed_to_bioproject(self, pmids: list[str]) -> dict[str, list[str]]:
        results = {pmid: [] for pmid in pmids}
        if not pmids:
            return results
        try:
            handle = Entrez.elink(
                dbfrom="pubmed", db="bioproject", id=",".join(pmids),
            )
            record = Entrez.read(handle)
            handle.close()
            for linkset in record:
                sid = linkset["IdList"][0] if linkset.get("IdList") else ""
                linked = []
                for db in linkset.get("LinkSetDb", []):
                    linked.extend(link["Id"] for link in db.get("Link", []))
                if sid in results:
                    results[sid] = linked
        except HTTPError as e:
            print(f"[WARN] ELink PubMed→BioProject failed: {e}")
        return results

    def _elink_pubmed_to_sra(self, pmids: list[str]) -> dict[str, list[str]]:
        results = {pmid: [] for pmid in pmids}
        if not pmids:
            return results
        try:
            handle = Entrez.elink(dbfrom="pubmed", db="sra", id=",".join(pmids))
            record = Entrez.read(handle)
            handle.close()
            for linkset in record:
                sid = linkset["IdList"][0] if linkset.get("IdList") else ""
                linked = []
                for db in linkset.get("LinkSetDb", []):
                    linked.extend(link["Id"] for link in db.get("Link", []))
                if sid in results:
                    results[sid] = linked
        except HTTPError as e:
            print(f"[WARN] ELink PubMed→SRA failed: {e}")
        return results

    # ── secondary filter ───────────────────────────────────────────────
    def _filter_non_human_skin(self, articles: list[dict]) -> list[dict]:
        filtered = []
        for art in articles:
            text = (
                (art.get("title") or "").lower() + " "
                + (art.get("abstract") or "").lower()
            )
            if not any(t in text for t in _SKIN_TERMS):
                continue
            if any(t in text for t in _HUMAN_EXCLUSIVE):
                continue
            filtered.append(art)
        return filtered

    # ── sampling site extraction ───────────────────────────────────────
    def extract_sampling_site(self, article: dict) -> str:
        text = (
            (article.get("title") or "").lower() + " "
            + (article.get("abstract") or "").lower()
        )
        best, best_len = None, 0
        for pat, site in _SAMPLING_SITE_PATTERNS:
            matches = re.findall(pat, text, re.IGNORECASE)
            if matches and len(matches) > best_len:
                best_len, best = len(matches), site
        return best or "N/A"

    # ── BioProject extraction (text-based, taxon-independent) ──────────
    def extract_bioproject_ids(self, article: dict) -> list[str]:
        text = (
            (article.get("title") or "") + " "
            + (article.get("abstract") or "")
        )
        ids = set()
        for pat in [r"PRJNA\d{4,}", r"PRJEB\d{4,}", r"PRJDB\d{4,}"]:
            ids.update(re.findall(pat, text))
        return sorted(ids)

    def extract_ena_ids(self, article: dict) -> list[str]:
        text = (
            (article.get("title") or "") + " "
            + (article.get("abstract") or "")
        )
        ids = set()
        for pat in [
            r"[ES]R[A-Z]\d{4,}", r"PRJ[A-Z]{2}\d+",
            r"SAM[NED]A?\d+", r"ERS\d+", r"SRS\d+",
        ]:
            ids.update(re.findall(pat, text))
        return sorted(ids)

    def resolve_bioproject_title(self, bioproject_id: str) -> str:
        try:
            handle = Entrez.esummary(db="bioproject", id=bioproject_id)
            summary = Entrez.read(handle)
            handle.close()
            s = summary[0] if isinstance(summary, list) else summary
            return str(s.get("title", s.get("Project_Title", "")))
        except Exception:
            return "N/A"
