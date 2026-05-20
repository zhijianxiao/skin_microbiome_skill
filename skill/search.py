"""PubMed search for non-human skin microbiome with ELink cross-database navigation.

Patterns adopted from bioSkills database-access:
  - entrez-search:  field-tag query syntax, history server, pagination
  - entrez-link:    cross-database navigation (PubMed → BioProject, PubMed → SRA)
  - entrez-fetch:   ESummary for quick metadata, EFetch for full records
  - sra-data:       SRA accession hierarchy
"""

import re
import time

from Bio import Entrez
from Bio.Entrez import HTTPError

# ── Constants ──────────────────────────────────────────────────────────
_SKIN_TERMS = [
    "skin", "cutaneous", "dermal", "dermis", "epidermal", "epidermis",
    "dermatitis", "dermatology", "dermatological", "eczema", "atopic",
    "seborrheic", "sebaceous", "keratinocyte", "melanocyte", "hair follicle",
    "sweat gland", "sebum",
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
    (r"\b(chin|mental region)\b", "Chin"),
    (r"\b(periocular|periocular|eyelid|eyelids|periorbital)\b", "Periocular"),
    (r"\b(axilla|axillae|armpit|axillary)\b", "Axilla"),
    (r"\b(neck|cervical|nape)\b", "Neck"),
    (r"\b(shoulder|shoulders|deltoid)\b", "Shoulder"),
    (r"\b(back|dorsal trunk|upper back|lower back|interscapular)\b", "Back"),
    (r"\b(chest|thoracic|sternal|pectoral)\b", "Chest"),
    (r"\b(abdomen|abdominal|belly|ventral)\b", "Abdomen"),
    (r"\b(groin|inguinal|inguinal region)\b", "Groin"),
    (r"\b(perineum|perineal|perianal|anal)\b", "Perineum"),
    (r"\b(buttock|buttocks|gluteal)\b", "Buttock"),
    (r"\b(forearm|volar forearm|antecubital|antecubital fossa)\b", "Forearm"),
    (r"\b(upper arm|arm|brachial)\b", "Upper arm"),
    (r"\b(hand|hands|palmar|dorsal hand|interdigital)\b", "Hand"),
    (r"\b(finger|fingers|fingertip|fingernail)\b", "Finger"),
    (r"\b(thigh|thighs|femoral)\b", "Thigh"),
    (r"\b(calf|calves|sural|lower leg|popliteal|popliteal fossa)\b", "Calf"),
    (r"\b(foot|feet|plantar|dorsal foot|toe|toes|interdigital foot)\b", "Foot"),
    (r"\b(paw|paws|footpad|footpads)\b", "Paw"),
    (r"\b(tail|tail base|tail skin|rump|withers)\b", "Tail"),
    (r"\b(mane|mane region)\b", "Mane"),
    (r"\b(fetlock|pastern|coronet|hoof)\b", "Hoof"),
    (r"\b(udder|teat|teats|mammary)\b", "Udder"),
    (r"\b(comb|wattle|wattles)\b", "Comb/Wattle"),
    (r"\b(wing|wings|wing web)\b", "Wing"),
    (r"\b(fin|fins|scale|scales|operculum)\b", "Fin"),
    (r"\b(oral cavity|oral|tongue|buccal mucosa|gingival|gingiva)\b", "Oral"),
    (r"\b(vaginal|vagina|cervicovaginal|vulvar|vulval)\b", "Vaginal"),
    (r"\b(conjunctiva|conjunctival|corneal|cornea)\b", "Conjunctival"),
    (r"\b(gut|intestinal|fecal|faecal|stool|colon|colonic)\b", "Gut"),
    (r"\b(respiratory|lung|pulmonary|bronchial|tracheal|nasopharyn)\b", "Respiratory"),
]


# ── PubMed record parsing ──────────────────────────────────────────────
def _parse_medline(record: dict) -> dict:
    """Parse Entrez.read() PubMed XML record into flat dict."""
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
                last = au.get("LastName", "")
                fore = au.get("ForeName", "")
                if last:
                    names.append(f"{last} {fore}".strip())
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


# ── SearchEngine ───────────────────────────────────────────────────────
class SearchEngine:
    """PubMed search + ELink cross-database navigation for non-human skin microbiome.

    Key patterns from bioSkills:
      - ESearch with [title/abstract] field tags and usehistory='y'
      - ELink dbfrom='pubmed' → db='bioproject' / 'sra' / 'biosample'
      - ESummary for quick BioProject metadata
      - Batch linking: pass comma-joined PMIDs to ELink
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
        species_latin: str,
        extra_keywords: str = "",
        max_results: int = None,
    ) -> list[dict]:
        """PubMed search → secondary filter → ELink BioProject/SRA → sampling site.

        Query (field-tag syntax from bioSkills entrez-search):
          ("skin microbiome"[title/abstract] OR "cutaneous microbiota"[title/abstract]
           OR "dermal microbiome"[title/abstract])
          AND ("{species_latin}") NOT human[mesh]
        """
        max_n = max_results or self.max_results

        # ── 1. Build query (field-tag pattern) ─────────────────────────
        query = self._build_query(species_latin, extra_keywords)

        # ── 2. ESearch (history server pattern for large sets) ──────────
        pmids = self._esearch(query, max_n)
        if not pmids:
            return []

        # ── 3. EFetch articles (medline XML) ───────────────────────────
        articles = self._efetch(pmids)

        # ── 4. Secondary filter: non-human skin ────────────────────────
        articles = self._filter_non_human_skin(articles)

        # ── 5. Extract sampling sites ──────────────────────────────────
        for art in articles:
            art["sampling_site"] = self.extract_sampling_site(art)

        # ── 6. ELink: PubMed → BioProject (cross-database pattern) ─────
        pmid_bioproject_map = self._elink_pubmed_to_bioproject(
            [a["pmid"] for a in articles]
        )

        # ── 7. Assign BioProject IDs to articles ───────────────────────
        for art in articles:
            art["bioproject_ids"] = pmid_bioproject_map.get(art["pmid"], [])

        return articles

    # ── query builder ──────────────────────────────────────────────────
    def _build_query(self, species_latin: str, extra_keywords: str = "") -> str:
        """Build field-tagged PubMed query per bioSkills entrez-search syntax."""
        skin_clause = (
            '("skin microbiome"[title/abstract] OR "cutaneous microbiota"[title/abstract]'
            ' OR "dermal microbiome"[title/abstract] OR "skin microbiota"[title/abstract]'
            ' OR "skin bacterial community"[title/abstract]'
            ' OR "skin fungal community"[title/abstract])'
        )
        species_clause = f'("{species_latin}")'
        query = f"{skin_clause} AND {species_clause} NOT human[mesh]"

        if extra_keywords:
            query = f"({query}) AND ({extra_keywords})"

        return query

    # ── ESearch ────────────────────────────────────────────────────────
    def _esearch(self, query: str, max_n: int) -> list[str]:
        """Run ESearch with pagination (pattern from entrez-search)."""
        try:
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=max_n,
                retmode="json",
                usehistory="n",
            )
            result = Entrez.read(handle)
            handle.close()
            return result.get("IdList", [])
        except HTTPError as e:
            print(f"[WARN] PubMed ESearch failed: {e}")
            print(f"       Query was: {query}")
            return []

    # ── EFetch ─────────────────────────────────────────────────────────
    def _efetch(self, pmids: list[str]) -> list[dict]:
        """Batch EFetch with medline XML (pattern from entrez-fetch)."""
        if not pmids:
            return []
        articles = []
        batch_size = 50
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            try:
                handle = Entrez.efetch(
                    db="pubmed",
                    id=",".join(batch),
                    rettype="medline",
                    retmode="xml",
                )
                records = Entrez.read(handle)
                handle.close()
                for rec in records.get("PubmedArticle", []):
                    articles.append(_parse_medline(rec))
            except HTTPError as e:
                print(f"[WARN] PubMed EFetch failed: {e}")
            time.sleep(0.34)  # NCBI rate limit
        return articles

    # ── ELink: PubMed → BioProject (key pattern from entrez-link) ──────
    def _elink_pubmed_to_bioproject(self, pmids: list[str]) -> dict[str, list[str]]:
        """Use ELink to find BioProject IDs linked to PubMed articles.

        Pattern from bioSkills entrez-link: batch_link() with
        dbfrom='pubmed', db='bioproject'.
        Falls back to text-based regex extraction.

        Returns {pmid: [PRJNAxxx, PRJEBxxx, ...]}
        """
        results = {pmid: [] for pmid in pmids}
        if not pmids:
            return results

        try:
            # Batch ELink: all PMIDs at once (entrez-link pattern)
            handle = Entrez.elink(
                dbfrom="pubmed",
                db="bioproject",
                id=",".join(pmids),
            )
            record = Entrez.read(handle)
            handle.close()

            # Each linkset corresponds to one input PMID
            for linkset in record:
                source_id = linkset["IdList"][0] if linkset.get("IdList") else ""
                linked = []
                for db in linkset.get("LinkSetDb", []):
                    linked.extend(link["Id"] for link in db.get("Link", []))
                if source_id in results:
                    results[source_id] = linked

        except HTTPError as e:
            print(f"[WARN] ELink PubMed→BioProject failed: {e}")

        return results

    def _elink_pubmed_to_sra(self, pmids: list[str]) -> dict[str, list[str]]:
        """ELink PubMed → SRA to find linked SRA experiments/runs.

        Pattern from bioSkills: entrez-link + sra-data accession hierarchy.
        """
        results = {pmid: [] for pmid in pmids}
        if not pmids:
            return results

        try:
            handle = Entrez.elink(dbfrom="pubmed", db="sra", id=",".join(pmids))
            record = Entrez.read(handle)
            handle.close()

            for linkset in record:
                source_id = linkset["IdList"][0] if linkset.get("IdList") else ""
                linked = []
                for db in linkset.get("LinkSetDb", []):
                    linked.extend(link["Id"] for link in db.get("Link", []))
                if source_id in results:
                    results[source_id] = linked
        except HTTPError as e:
            print(f"[WARN] ELink PubMed→SRA failed: {e}")

        return results

    # ── BioProject resolution via ESummary (entrez-fetch pattern) ──────
    def resolve_bioproject_title(self, bioproject_id: str) -> str:
        """Get BioProject title via ESummary (entrez-fetch pattern)."""
        try:
            handle = Entrez.esummary(db="bioproject", id=bioproject_id)
            summary = Entrez.read(handle)
            handle.close()
            s = summary[0] if isinstance(summary, list) else summary
            return str(s.get("title", s.get("Project_Title", "")))
        except Exception:
            return "N/A"

    # ── secondary filter ───────────────────────────────────────────────
    def _filter_non_human_skin(self, articles: list[dict]) -> list[dict]:
        """Keep only articles mentioning skin terms AND NOT human subjects."""
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
        best = None
        best_len = 0
        for pat, site_name in _SAMPLING_SITE_PATTERNS:
            matches = re.findall(pat, text, re.IGNORECASE)
            if matches and len(matches) > best_len:
                best_len = len(matches)
                best = site_name
        return best or "N/A"

    # ── legacy: text-based BioProject extraction (fallback) ────────────
    def extract_bioproject_ids(self, article: dict) -> list[str]:
        """Regex fallback for BioProject ID extraction."""
        text = (
            (article.get("title") or "") + " "
            + (article.get("abstract") or "")
        )
        ids = set()
        for pat in [r"PRJNA\d{4,}", r"PRJEB\d{4,}", r"PRJDB\d{4,}"]:
            ids.update(re.findall(pat, text))
        return sorted(ids)

    def extract_ena_ids(self, article: dict) -> list[str]:
        """Regex extraction of all ENA/SRA accessions."""
        text = (
            (article.get("title") or "") + " "
            + (article.get("abstract") or "")
        )
        patterns = [
            r"[ES]R[A-Z]\d{4,}", r"PRJ[A-Z]{2}\d+",
            r"SAM[NED]A?\d+", r"ERS\d+", r"SRS\d+",
        ]
        ids = set()
        for pat in patterns:
            ids.update(re.findall(pat, text))
        return sorted(ids)
