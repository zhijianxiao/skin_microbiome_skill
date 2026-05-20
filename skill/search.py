"""PubMed search for non-human skin microbiome literature."""

import re
import time

from Bio import Entrez
from Bio.Entrez import HTTPError


# ── Skin-related terms for secondary filtering ─────────────────────────
_SKIN_TERMS = [
    "skin", "cutaneous", "dermal", "dermis", "epidermal", "epidermis",
    "dermatitis", "dermatology", "dermatological", "eczema", "atopic",
    "seborrheic", "sebaceous", "keratinocyte", "melanocyte", "hair follicle",
    "sweat gland", "sebum",
]

# ── Human-exclusive terms to exclude ───────────────────────────────────
_HUMAN_EXCLUSIVE = [
    "patient", "patients", "volunteer", "volunteers", "human subject",
    "clinical trial", "healthy adult", "healthy adults",
]

# ── Sampling site anatomical terms ─────────────────────────────────────
_SAMPLING_SITE_PATTERNS = [
    # Head / Face
    (r"\b(ear|ears|auricular|otic)\b", "Ear"),
    (r"\b(nose|nasal|nares|nostril)\b", "Nose"),
    (r"\b(cheek|cheeks|buccal|malar)\b", "Cheek"),
    (r"\b(forehead|frontal)\b", "Forehead"),
    (r"\b(scalp|scalps)\b", "Scalp"),
    (r"\b(chin|mental region)\b", "Chin"),
    (r"\b(periocular|periocular|eyelid|eyelids|periorbital)\b", "Periocular"),
    # Upper body
    (r"\b(axilla|axillae|armpit|axillary)\b", "Axilla"),
    (r"\b(neck|cervical|nape)\b", "Neck"),
    (r"\b(shoulder|shoulders|deltoid)\b", "Shoulder"),
    (r"\b(back|dorsal trunk|upper back|lower back|interscapular)\b", "Back"),
    (r"\b(chest|thoracic|sternal|pectoral)\b", "Chest"),
    # Lower body
    (r"\b(abdomen|abdominal|belly|ventral)\b", "Abdomen"),
    (r"\b(groin|inguinal|inguinal region)\b", "Groin"),
    (r"\b(perineum|perineal|perianal|anal)\b", "Perineum"),
    (r"\b(buttock|buttocks|gluteal)\b", "Buttock"),
    # Limbs
    (r"\b(forearm|volar forearm|antecubital|antecubital fossa)\b", "Forearm"),
    (r"\b(upper arm|arm|brachial)\b", "Upper arm"),
    (r"\b(hand|hands|palmar|dorsal hand|interdigital)\b", "Hand"),
    (r"\b(finger|fingers|fingertip|fingernail)\b", "Finger"),
    (r"\b(thigh|thighs|femoral)\b", "Thigh"),
    (r"\b(calf|calves|sural|lower leg|popliteal|popliteal fossa)\b", "Calf"),
    (r"\b(foot|feet|plantar|dorsal foot|toe|toes|interdigital foot)\b", "Foot"),
    (r"\b(paw|paws|footpad|footpads)\b", "Paw"),
    # Animal-specific
    (r"\b(tail|tail base|tail skin|rump|withers)\b", "Tail"),
    (r"\b(mane|mane region)\b", "Mane"),
    (r"\b(fetlock|pastern|coronet|hoof)\b", "Hoof"),
    (r"\b(udder|teat|teats|mammary)\b", "Udder"),
    (r"\b(comb|wattle|wattles)\b", "Comb/Wattle"),
    (r"\b(wing|wings|wing web)\b", "Wing"),
    (r"\b(fin|fins|scale|scales|operculum)\b", "Fin"),
    # Mucosal
    (r"\b(oral cavity|oral|tongue|buccal mucosa|gingival|gingiva)\b", "Oral"),
    (r"\b(vaginal|vagina|cervicovaginal|vulvar|vulval)\b", "Vaginal"),
    (r"\b(conjunctiva|conjunctival|corneal|cornea)\b", "Conjunctival"),
    (r"\b(gut|intestinal|fecal|faecal|stool|colon|colonic)\b", "Gut"),
    (r"\b(respiratory|lung|pulmonary|bronchial|tracheal|nasopharyn)\b", "Respiratory"),
]


def _parse_pubmed_record(record: dict) -> dict:
    """Parse a PubMed XML record into a flat dict."""
    article = {}
    try:
        medline = record.get("MedlineCitation", record)
        art = medline.get("Article", {})

        article["pmid"] = str(medline.get("PMID", ""))

        # Title
        article["title"] = art.get("ArticleTitle", "")

        # Authors
        authors = art.get("AuthorList", [])
        if isinstance(authors, list):
            names = []
            for a in authors:
                last = a.get("LastName", "")
                fore = a.get("ForeName", "")
                if last:
                    names.append(f"{last} {fore}".strip())
            article["authors"] = "; ".join(names[:10])
            if len(names) > 10:
                article["authors"] += " et al."
        else:
            article["authors"] = ""

        # Journal + Year
        journal = art.get("Journal", {})
        article["journal"] = journal.get("Title", "")
        date_info = journal.get("JournalIssue", {}).get("PubDate", {})
        article["year"] = str(date_info.get("Year") or date_info.get("MedlineDate", ""))

        # DOI
        article["doi"] = ""
        eid_list = art.get("ELocationID", [])
        if isinstance(eid_list, dict):
            eid_list = [eid_list]
        for eid in eid_list or []:
            if isinstance(eid, dict) and eid.get("EIdType") == "doi":
                article["doi"] = str(eid.get("value", eid))
                break

        # Abstract
        abstract_parts = art.get("Abstract", {}).get("AbstractText", [])
        if isinstance(abstract_parts, str):
            article["abstract"] = abstract_parts
        elif isinstance(abstract_parts, list):
            article["abstract"] = " ".join(str(p) for p in abstract_parts)
        else:
            article["abstract"] = ""

    except Exception:
        pass

    return article


class SearchEngine:
    """PubMed search for non-human skin microbiome, with secondary filtering."""

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
        species_latin: str,
        extra_keywords: str = "",
        max_results: int = None,
    ) -> list[dict]:
        """Search PubMed for non-human skin microbiome literature.

        Builds query:
          ("skin microbiome" OR "cutaneous microbiota" OR "dermal microbiome")
          AND ("{species_latin}") NOT human

        Then applies secondary filters:
          - Title/abstract must contain skin-related terms
          - Must not be human-focused
          - Extracts sampling site from abstract

        Returns:
          List of article dicts with keys: pmid, title, authors, journal,
          year, doi, abstract, sampling_site, bioproject_ids.
        """
        max_n = max_results or self.max_results

        # ── Build PubMed query ──
        skin_clause = (
            '("skin microbiome" OR "cutaneous microbiota"'
            ' OR "dermal microbiome" OR "skin microbiota"'
            ' OR "skin bacterial community" OR "skin fungal community")'
        )
        species_clause = f'("{species_latin}")'
        query = f"{skin_clause} AND {species_clause} NOT human"

        if extra_keywords:
            query = f"({query}) AND ({extra_keywords})"

        # ── ESearch ──
        pmids = self._esearch(query, max_n)
        if not pmids:
            return []

        # ── EFetch ──
        articles = self._efetch(pmids)

        # ── Secondary filter: non-human skin ──
        articles = self._filter_non_human_skin(articles)

        # ── Extract sampling site + BioProject IDs ──
        for art in articles:
            art["sampling_site"] = self.extract_sampling_site(art)
            art["bioproject_ids"] = self.extract_bioproject_ids(art)

        return articles

    # ── PubMed I/O ─────────────────────────────────────────────────────
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
                    articles.append(_parse_pubmed_record(rec))
            except HTTPError as e:
                print(f"[WARN] PubMed EFetch failed: {e}")
            time.sleep(0.34)
        return articles

    # ── secondary filter ───────────────────────────────────────────────
    def _filter_non_human_skin(self, articles: list[dict]) -> list[dict]:
        """Remove articles that are NOT about non-human skin microbiome."""
        filtered = []
        for art in articles:
            title = (art.get("title") or "").lower()
            abstract = (art.get("abstract") or "").lower()
            text = title + " " + abstract

            # Must mention skin-related terms
            if not any(term in text for term in _SKIN_TERMS):
                continue

            # Must NOT be primarily about humans
            if any(term in text for term in _HUMAN_EXCLUSIVE):
                continue

            filtered.append(art)
        return filtered

    # ── sampling site extraction ───────────────────────────────────────
    def extract_sampling_site(self, article: dict) -> str:
        """Extract anatomical sampling site from title + abstract.

        Returns site name, or 'N/A' if not identifiable.
        """
        title = (article.get("title") or "").lower()
        abstract = (article.get("abstract") or "").lower()
        text = title + " " + abstract

        best_match = None
        best_len = 0
        for pattern, site_name in _SAMPLING_SITE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                match_len = len(matches)
                if match_len > best_len:
                    best_len = match_len
                    best_match = site_name

        return best_match or "N/A"

    # ── BioProject ID extraction ───────────────────────────────────────
    def extract_bioproject_ids(self, article: dict) -> list[str]:
        """Extract metagenomic BioProject IDs (PRJNAxxx / PRJEBxxx) from article text.

        Returns list of unique IDs, or empty list.
        """
        text = (
            (article.get("title") or "")
            + " "
            + (article.get("abstract") or "")
        )
        # BioProject patterns
        patterns = [
            r"PRJNA\d{4,}",
            r"PRJEB\d{4,}",
            r"PRJDB\d{4,}",
        ]
        ids = set()
        for pat in patterns:
            ids.update(re.findall(pat, text))
        return sorted(ids)

    def extract_ena_ids(self, article: dict) -> list[str]:
        """Extract all ENA/SRA accession IDs (runs + bioprojects + samples)."""
        text = (
            (article.get("title") or "")
            + " "
            + (article.get("abstract") or "")
        )
        patterns = [
            r"[ES]R[A-Z]\d{4,}",
            r"PRJ[A-Z]{2}\d+",
            r"SAM[NED]A?\d+",
            r"ERS\d+",
            r"SRS\d+",
        ]
        ids = set()
        for pat in patterns:
            ids.update(re.findall(pat, text))
        return sorted(ids)
