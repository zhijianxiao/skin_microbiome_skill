"""Species name normalization via NCBI Taxonomy (dynamic, no fixed lists).

Patterns adopted from bioSkills database-access/entrez-search:
  - ESearch with field qualifiers [scin], [comn]
  - ESummary for quick taxonomy metadata
  - ELink / ESearch for child taxa expansion

Key design:
  - normalize() — Chinese/English/Latin → canonical record (NCBI API)
  - expand_search_terms() — canonical record → list of Boolean OR terms
    for PubMed query covering common names, synonyms, and child genera
"""

import re

from Bio import Entrez

# ── Fast-path local cache: common laboratory / veterinary animals ─────
_LOCAL_CACHE = {
    "马":   ("Horse",          "Equus caballus",         "9796"),
    "鼠":   ("Mouse",          "Mus musculus",           "10090"),
    "小鼠":  ("Mouse",          "Mus musculus",           "10090"),
    "大鼠":  ("Rat",            "Rattus norvegicus",      "10116"),
    "狗":   ("Dog",            "Canis lupus familiaris", "9615"),
    "犬":   ("Dog",            "Canis lupus familiaris", "9615"),
    "猫":   ("Cat",            "Felis catus",            "9685"),
    "兔":   ("Rabbit",         "Oryctolagus cuniculus",  "9986"),
    "家兔":  ("Rabbit",         "Oryctolagus cuniculus",  "9986"),
    "猪":   ("Pig",            "Sus scrofa domesticus",  "9825"),
    "牛":   ("Cattle",         "Bos taurus",             "9913"),
    "奶牛":  ("Cattle",         "Bos taurus",             "9913"),
    "绵羊":  ("Sheep",          "Ovis aries",             "9940"),
    "山羊":  ("Goat",           "Capra hircus",           "9925"),
    "斑马鱼": ("Zebrafish",     "Danio rerio",            "7955"),
    "豚鼠":  ("Guinea pig",     "Cavia porcellus",        "10141"),
    "仓鼠":  ("Hamster",        "Mesocricetus auratus",   "10036"),
    "鸡":   ("Chicken",        "Gallus gallus domesticus","9031"),
    "猴":   ("Rhesus macaque", "Macaca mulatta",         "9544"),
    "恒河猴": ("Rhesus macaque", "Macaca mulatta",         "9544"),
}


class SpeciesManager:
    """Dynamic species normalization via NCBI Taxonomy.

    No fixed species list — any organism in NCBI Taxonomy is supported.
    Local cache provides fast path for common laboratory animals.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        sc = self.config.get("search", {})
        Entrez.email = sc.get("email", "user@example.com")
        if sc.get("api_key"):
            Entrez.api_key = sc["api_key"]

    # ═══════════════════════════════════════════════════════════════════
    #  Primary API
    # ═══════════════════════════════════════════════════════════════════

    def normalize(self, name: str) -> dict | None:
        """Chinese / English / Latin → canonical species record.

        Lookup order:
          1. Local cache exact match
          2. Local cache fuzzy match
          3. NCBI Taxonomy API (common name) → returns scientific name + taxon_id
          4. NCBI Taxonomy API (scientific name)

        Returns dict: {chinese, english, latin, taxon_id, synonyms}
        """
        if not name:
            return None
        q = name.strip()

        # 1) Local exact
        r = self._cache_exact(q)
        if r:
            return r

        # 2) Local fuzzy
        r = self._cache_fuzzy(q)
        if r:
            return r

        # 3) NCBI Taxonomy — try common name then scientific
        for field in ("[comn]", "[scin]"):
            r = self._ncbi_lookup(q, field)
            if r:
                return r

        return None

    # ═══════════════════════════════════════════════════════════════════
    #  Search term expansion (for Boolean PubMed queries)
    # ═══════════════════════════════════════════════════════════════════

    def expand_search_terms(self, species_info: dict) -> dict:
        """Expand a canonical species record into Boolean-ready search terms.

        Returns dict with keys suitable for building PubMed queries:
          {
            "canonical":  "Selachii",          # scientific name
            "common":     "sharks",            # common name
            "synonyms":   ["Selachii", ...],   # scientific synonyms from NCBI
            "genera":     ["Carcharhinus", "Galeocerdo", ...],  # child genera
            "all":        ["shark","sharks","Selachii","Carcharhinus","Galeocerdo",...],
            "boolean_clause": '("shark" OR "sharks" OR "Selachii" OR ...)',
          }
        """
        latin = species_info.get("latin", "")
        english = species_info.get("english", "")
        taxon_id = species_info.get("taxon_id", "")

        # Synonym lookup via NCBI Taxonomy
        synonyms = self._ncbi_synonyms(taxon_id) if taxon_id else []

        # Child genera lookup (for broader coverage)
        genera = self._ncbi_child_genera(taxon_id, limit=8) if taxon_id else []

        # Build term pools
        common_terms = []
        if english:
            common_terms.extend([english, english.rstrip("s")])
            if english.endswith("s"):
                common_terms.append(english[:-1])
            else:
                common_terms.append(english + "s")
            common_terms = list(dict.fromkeys(common_terms))

        sci_terms = [latin] if latin else []
        sci_terms.extend(s for s in synonyms if s.lower() != latin.lower())
        sci_terms = list(dict.fromkeys(sci_terms))

        # Add broader parent taxa (class, order, family) for wider coverage
        parent_terms = self._ncbi_parent_taxa(taxon_id) if taxon_id else []

        # Merge all, deduplicate
        all_terms = list(dict.fromkeys(common_terms + sci_terms + genera + parent_terms))

        # Build Boolean OR clause for PubMed
        clause_parts = [f'"{t}"' for t in all_terms]
        boolean_clause = "(" + " OR ".join(clause_parts) + ")"

        return {
            "canonical":       latin,
            "common":          english,
            "synonyms":        synonyms,
            "genera":          genera,
            "parent_terms":    parent_terms,
            "all":             all_terms,
            "boolean_clause":  boolean_clause,
        }

    # ═══════════════════════════════════════════════════════════════════
    #  NCBI Taxonomy helpers
    # ═══════════════════════════════════════════════════════════════════

    def _ncbi_lookup(self, name: str, field: str) -> dict | None:
        """Query NCBI Taxonomy by name + field qualifier."""
        try:
            handle = Entrez.esearch(
                db="taxonomy", term=f"{name}{field}", retmax=3
            )
            record = Entrez.read(handle)
            handle.close()
            ids = record.get("IdList", [])
            if not ids:
                return None

            handle = Entrez.esummary(db="taxonomy", id=ids[0])
            summary = Entrez.read(handle)
            handle.close()
            s = summary[0]
            sci = s.get("ScientificName", "")
            com = s.get("CommonName", "")
            syn_list = s.get("SynonymList", [])
            if isinstance(syn_list, str):
                syn_list = [syn_list] if syn_list else []

            if sci:
                return {
                    "chinese":   name,
                    "english":   com or name,
                    "latin":     sci,
                    "taxon_id":  ids[0],
                    "synonyms":  syn_list,
                }
        except Exception as e:
            print(f"  [WARN] NCBI Taxonomy lookup failed for '{name}': {e}")
        return None

    def _ncbi_synonyms(self, taxon_id: str) -> list[str]:
        """Get scientific name synonyms for a taxon via ESummary."""
        try:
            handle = Entrez.esummary(db="taxonomy", id=taxon_id)
            summary = Entrez.read(handle)
            handle.close()
            s = summary[0]
            syn = s.get("SynonymList", [])
            if isinstance(syn, str):
                return [syn] if syn else []
            return list(syn) if syn else []
        except Exception:
            return []

    def _ncbi_child_genera(self, taxon_id: str, limit: int = 8) -> list[str]:
        """Find common child genera/species under a parent taxon.

        Uses ESearch: txid{taxon_id}[orgn] to find child records,
        then extracts genus-level names and well-known species.

        Filters out unnamed "sp." entries and keeps only clean names
        that are likely to appear in PubMed titles.
        """
        try:
            handle = Entrez.esearch(
                db="taxonomy",
                term=f"txid{taxon_id}[orgn] AND species[rank]",
                retmax=60,
                sort="relevance",
            )
            record = Entrez.read(handle)
            handle.close()
            child_ids = record.get("IdList", [])[:limit * 3]

            if not child_ids:
                return []

            handle = Entrez.esummary(db="taxonomy", id=",".join(child_ids))
            summaries = Entrez.read(handle)
            handle.close()

            genera = []
            seen = set()
            for s in summaries:
                sci = s.get("ScientificName", "")
                genus = s.get("Genus", "")

                # Skip unnamed / unidentified species
                if "sp." in sci.lower() or "cf." in sci.lower():
                    continue

                # Add clean genus name (single word, capitalized, no numbers)
                if genus and genus not in seen:
                    if re.match(r"^[A-Z][a-z]+$", genus):
                        genera.append(genus)
                        seen.add(genus)

                # Add full scientific name if it's a clean binomial
                if sci and sci not in seen:
                    if re.match(r"^[A-Z][a-z]+\s[a-z]+$", sci):
                        genera.append(sci)
                        seen.add(sci)

                if len(genera) >= limit:
                    break

            return genera[:limit]

        except Exception as e:
            print(f"  [WARN] NCBI child genera lookup failed for {taxon_id}: {e}")
            return []

    def _ncbi_parent_taxa(self, taxon_id: str) -> list[str]:
        """Get broader taxonomic group names (class, order, family).

        For sharks (Selachii), this would return Elasmobranchii,
        Chondrichthyes, etc. — broader terms that authors may use.
        """
        try:
            handle = Entrez.esummary(db="taxonomy", id=taxon_id)
            summary = Entrez.read(handle)
            handle.close()
            s = summary[0]
            lineage = s.get("LineageEx", [])
            broader = []
            for node in lineage[-4:]:  # last 4 levels: family, order, class, phylum
                sci = node.get("ScientificName", "")
                rank = node.get("Rank", "")
                if sci and rank not in ("genus", "species", "subspecies"):
                    broader.append(sci)
            return broader
        except Exception:
            return []

    # ═══════════════════════════════════════════════════════════════════
    #  Local cache helpers
    # ═══════════════════════════════════════════════════════════════════

    def _cache_exact(self, q: str) -> dict | None:
        ql = q.lower()
        for cn, (en, la, tx) in _LOCAL_CACHE.items():
            if ql in (cn.lower(), en.lower(), la.lower()):
                return {
                    "chinese": cn, "english": en, "latin": la,
                    "taxon_id": tx, "synonyms": [],
                }
        return None

    def _cache_fuzzy(self, q: str) -> dict | None:
        ql = q.lower()
        for cn, (en, la, tx) in _LOCAL_CACHE.items():
            if (ql in cn.lower() or ql in en.lower() or ql in la.lower()):
                return {
                    "chinese": cn, "english": en, "latin": la,
                    "taxon_id": tx, "synonyms": [],
                }
        return None

    # ═══════════════════════════════════════════════════════════════════
    #  Convenience methods
    # ═══════════════════════════════════════════════════════════════════

    def get_info(self, species_name: str) -> dict:
        result = self.normalize(species_name)
        if result is None:
            return {"error": f"Species not found: {species_name}"}
        return result

    def list_all(self) -> list[dict]:
        return [
            {"chinese": cn, "english": en, "latin": la, "taxon_id": tx}
            for cn, (en, la, tx) in _LOCAL_CACHE.items()
        ]

    def list_animals(self) -> list[dict]:
        return self.list_all()

    def search(self, keyword: str) -> list[dict]:
        kw = keyword.strip().lower()
        results = []
        for cn, (en, la, tx) in _LOCAL_CACHE.items():
            if (kw in cn.lower() or kw in en.lower() or kw in la.lower()):
                results.append({
                    "chinese": cn, "english": en, "latin": la,
                    "taxon_id": tx, "synonyms": [],
                })
        return results
