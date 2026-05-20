"""Species name normalization using NCBI Taxonomy + local fallback.

Patterns adopted from bioSkills database-access/entrez-search:
  - ESearch with field qualifiers [scin], [comn]
  - ESummary for quick taxonomy metadata
  - Local cache as fallback
"""

from Bio import Entrez

# ── Local species cache (fallback when offline) ────────────────────────
_LOCAL_DB = {
    "马":   {"chinese": "马",   "english": "Horse",            "latin": "Equus caballus",          "taxon_id": "9796"},
    "鼠":   {"chinese": "鼠",   "english": "Mouse",            "latin": "Mus musculus",            "taxon_id": "10090"},
    "小鼠":  {"chinese": "小鼠", "english": "Mouse",           "latin": "Mus musculus",            "taxon_id": "10090"},
    "大鼠":  {"chinese": "大鼠", "english": "Rat",             "latin": "Rattus norvegicus",       "taxon_id": "10116"},
    "狗":   {"chinese": "狗",   "english": "Dog",              "latin": "Canis lupus familiaris",  "taxon_id": "9615"},
    "犬":   {"chinese": "犬",   "english": "Dog",              "latin": "Canis lupus familiaris",  "taxon_id": "9615"},
    "猫":   {"chinese": "猫",   "english": "Cat",              "latin": "Felis catus",             "taxon_id": "9685"},
    "兔":   {"chinese": "兔",   "english": "Rabbit",           "latin": "Oryctolagus cuniculus",   "taxon_id": "9986"},
    "家兔":  {"chinese": "家兔", "english": "Rabbit",          "latin": "Oryctolagus cuniculus",   "taxon_id": "9986"},
    "猪":   {"chinese": "猪",   "english": "Pig",              "latin": "Sus scrofa domesticus",   "taxon_id": "9825"},
    "牛":   {"chinese": "牛",   "english": "Cattle",           "latin": "Bos taurus",              "taxon_id": "9913"},
    "奶牛":  {"chinese": "奶牛", "english": "Cattle",          "latin": "Bos taurus",              "taxon_id": "9913"},
    "绵羊":  {"chinese": "绵羊", "english": "Sheep",           "latin": "Ovis aries",              "taxon_id": "9940"},
    "山羊":  {"chinese": "山羊", "english": "Goat",            "latin": "Capra hircus",            "taxon_id": "9925"},
    "斑马鱼": {"chinese": "斑马鱼","english": "Zebrafish",      "latin": "Danio rerio",             "taxon_id": "7955"},
    "豚鼠":  {"chinese": "豚鼠", "english": "Guinea pig",      "latin": "Cavia porcellus",         "taxon_id": "10141"},
    "仓鼠":  {"chinese": "仓鼠", "english": "Hamster",         "latin": "Mesocricetus auratus",    "taxon_id": "10036"},
    "鸡":   {"chinese": "鸡",   "english": "Chicken",          "latin": "Gallus gallus domesticus","taxon_id": "9031"},
    "猴":   {"chinese": "猴",   "english": "Rhesus macaque",   "latin": "Macaca mulatta",          "taxon_id": "9544"},
    "恒河猴": {"chinese": "恒河猴","english": "Rhesus macaque", "latin": "Macaca mulatta",          "taxon_id": "9544"},
}


class SpeciesManager:
    """Normalize species names via NCBI Taxonomy (Entrez), fallback to local DB.

    Patterns from bioSkills:
      - entrez-search:  ESearch(db='taxonomy', term='Equus caballus[scin]')
      - entrez-fetch:   ESummary for quick taxonomy metadata
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        sc = self.config.get("search", {})
        Entrez.email = sc.get("email", "user@example.com")
        if sc.get("api_key"):
            Entrez.api_key = sc["api_key"]

    # ── normalize (primary API) ────────────────────────────────────────
    def normalize(self, name: str) -> dict | None:
        """Chinese/English/Latin → canonical species record.

        Strategy:
          1) Exact match in local cache (fast path)
          2) Substring fuzzy in local cache
          3) NCBI Taxonomy ESearch (dynamic lookup)
        """
        if not name:
            return None
        q = name.strip()

        # 1) Local: exact match
        result = self._local_exact(q)
        if result:
            return result

        # 2) Local: fuzzy substring
        result = self._local_fuzzy(q)
        if result:
            return result

        # 3) NCBI Taxonomy API
        result = self._ncbi_taxonomy_lookup(q)
        if result:
            return result

        return None

    # ── local helpers ──────────────────────────────────────────────────
    def _local_exact(self, q: str) -> dict | None:
        ql = q.lower()
        for entry in _LOCAL_DB.values():
            if (ql == entry["chinese"].lower()
                or ql == entry["english"].lower()
                or ql == entry["latin"].lower()):
                return dict(entry)
        return None

    def _local_fuzzy(self, q: str) -> dict | None:
        ql = q.lower()
        for entry in _LOCAL_DB.values():
            if (ql in entry["chinese"].lower()
                or ql in entry["english"].lower()
                or ql in entry["latin"].lower()):
                return dict(entry)
        return None

    # ── NCBI Taxonomy lookup ───────────────────────────────────────────
    def _ncbi_taxonomy_lookup(self, name: str) -> dict | None:
        """Query NCBI Taxonomy via ESearch + ESummary.

        Pattern from bioSkills entrez-search: field-tagged query.
        Pattern from bioSkills entrez-fetch: ESummary for metadata.
        """
        try:
            # Try scientific name first, then common name
            for field in ("[scin]", "[comn]"):
                term = f"{name}{field}"
                handle = Entrez.esearch(db="taxonomy", term=term, retmax=5)
                record = Entrez.read(handle)
                handle.close()

                id_list = record.get("IdList", [])
                if not id_list:
                    continue

                # Use ESummary for quick metadata (entrez-fetch pattern)
                taxon_id = id_list[0]
                handle = Entrez.esummary(db="taxonomy", id=taxon_id)
                summary = Entrez.read(handle)
                handle.close()

                s = summary[0]
                sci_name = s.get("ScientificName", "")
                com_name = s.get("CommonName", "")

                if sci_name:
                    return {
                        "chinese": name,
                        "english": com_name or name,
                        "latin": sci_name,
                        "taxon_id": taxon_id,
                    }
        except Exception as e:
            print(f"  [WARN] NCBI Taxonomy lookup failed for '{name}': {e}")

        return None

    # ── batch access ───────────────────────────────────────────────────
    def get_info(self, species_name: str) -> dict:
        result = self.normalize(species_name)
        if result is None:
            return {"error": f"Species not found: {species_name}"}
        return result

    def list_all(self) -> list[dict]:
        return [dict(e) for e in _LOCAL_DB.values()]

    def list_animals(self) -> list[dict]:
        return [dict(e) for e in _LOCAL_DB.values()]

    def search(self, keyword: str) -> list[dict]:
        kw = keyword.strip().lower()
        results = []
        for entry in _LOCAL_DB.values():
            if (kw in entry["chinese"].lower()
                or kw in entry["english"].lower()
                or kw in entry["latin"].lower()):
                results.append(dict(entry))
        return results
