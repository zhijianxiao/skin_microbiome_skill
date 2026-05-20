"""Species name normalization: Chinese → English → Latin for non-human hosts."""

# ── Non-human animal hosts (primary use case) ──────────────────────────
_SPECIES_DB = [
    # ── Common laboratory / veterinary animals ──
    {
        "chinese": "马",
        "english": "Horse",
        "latin": "Equus caballus",
        "taxon_id": "9796",
    },
    {
        "chinese": "鼠",
        "english": "Mouse",
        "latin": "Mus musculus",
        "taxon_id": "10090",
    },
    {
        "chinese": "小鼠",
        "english": "Mouse",
        "latin": "Mus musculus",
        "taxon_id": "10090",
    },
    {
        "chinese": "大鼠",
        "english": "Rat",
        "latin": "Rattus norvegicus",
        "taxon_id": "10116",
    },
    {
        "chinese": "狗",
        "english": "Dog",
        "latin": "Canis lupus familiaris",
        "taxon_id": "9615",
    },
    {
        "chinese": "犬",
        "english": "Dog",
        "latin": "Canis lupus familiaris",
        "taxon_id": "9615",
    },
    {
        "chinese": "猫",
        "english": "Cat",
        "latin": "Felis catus",
        "taxon_id": "9685",
    },
    {
        "chinese": "兔",
        "english": "Rabbit",
        "latin": "Oryctolagus cuniculus",
        "taxon_id": "9986",
    },
    {
        "chinese": "家兔",
        "english": "Rabbit",
        "latin": "Oryctolagus cuniculus",
        "taxon_id": "9986",
    },
    {
        "chinese": "猪",
        "english": "Pig",
        "latin": "Sus scrofa domesticus",
        "taxon_id": "9825",
    },
    {
        "chinese": "牛",
        "english": "Cattle",
        "latin": "Bos taurus",
        "taxon_id": "9913",
    },
    {
        "chinese": "奶牛",
        "english": "Cattle",
        "latin": "Bos taurus",
        "taxon_id": "9913",
    },
    {
        "chinese": "绵羊",
        "english": "Sheep",
        "latin": "Ovis aries",
        "taxon_id": "9940",
    },
    {
        "chinese": "山羊",
        "english": "Goat",
        "latin": "Capra hircus",
        "taxon_id": "9925",
    },
    {
        "chinese": "斑马鱼",
        "english": "Zebrafish",
        "latin": "Danio rerio",
        "taxon_id": "7955",
    },
    {
        "chinese": "豚鼠",
        "english": "Guinea pig",
        "latin": "Cavia porcellus",
        "taxon_id": "10141",
    },
    {
        "chinese": "仓鼠",
        "english": "Hamster",
        "latin": "Mesocricetus auratus",
        "taxon_id": "10036",
    },
    {
        "chinese": "鸡",
        "english": "Chicken",
        "latin": "Gallus gallus domesticus",
        "taxon_id": "9031",
    },
    {
        "chinese": "猴",
        "english": "Monkey",
        "latin": "Macaca mulatta",
        "taxon_id": "9544",
    },
    {
        "chinese": "恒河猴",
        "english": "Rhesus macaque",
        "latin": "Macaca mulatta",
        "taxon_id": "9544",
    },
    # ── Common skin microbiome microbes (for reference) ──
    {
        "chinese": "表皮葡萄球菌",
        "english": "Staphylococcus epidermidis",
        "latin": "Staphylococcus epidermidis",
        "taxon_id": "1282",
    },
    {
        "chinese": "金黄色葡萄球菌",
        "english": "Staphylococcus aureus",
        "latin": "Staphylococcus aureus",
        "taxon_id": "1280",
    },
    {
        "chinese": "痤疮丙酸杆菌",
        "english": "Cutibacterium acnes",
        "latin": "Cutibacterium acnes",
        "taxon_id": "1747",
    },
    {
        "chinese": "马拉色菌",
        "english": "Malassezia restricta",
        "latin": "Malassezia restricta",
        "taxon_id": "76775",
    },
    {
        "chinese": "糠秕马拉色菌",
        "english": "Malassezia globosa",
        "latin": "Malassezia globosa",
        "taxon_id": "554073",
    },
    {
        "chinese": "铜绿假单胞菌",
        "english": "Pseudomonas aeruginosa",
        "latin": "Pseudomonas aeruginosa",
        "taxon_id": "287",
    },
    {
        "chinese": "化脓性链球菌",
        "english": "Streptococcus pyogenes",
        "latin": "Streptococcus pyogenes",
        "taxon_id": "1314",
    },
    {
        "chinese": "微球菌",
        "english": "Micrococcus luteus",
        "latin": "Micrococcus luteus",
        "taxon_id": "1270",
    },
]


class SpeciesManager:
    """Maps Chinese/English species names to standard English + Latin forms."""

    def __init__(self, config: dict = None):
        self.config = config or {}

    # ── normalization ──────────────────────────────────────────────────
    def normalize(self, name: str) -> dict | None:
        """Normalize Chinese, English, or Latin input to a canonical record.

        Returns dict with: chinese, english, latin, taxon_id, or None.
        """
        if not name:
            return None

        q = name.strip().lower()

        # 1) Exact match across any field
        for entry in _SPECIES_DB:
            if (
                q == entry["chinese"].lower()
                or q == entry["english"].lower()
                or q == entry["latin"].lower()
            ):
                return dict(entry)

        # 2) Substring fuzzy match
        for entry in _SPECIES_DB:
            if (
                q in entry["chinese"].lower()
                or q in entry["english"].lower()
                or q in entry["latin"].lower()
            ):
                return dict(entry)

        return None

    def get_info(self, species_name: str) -> dict:
        result = self.normalize(species_name)
        if result is None:
            return {"error": f"Species not found: {species_name}"}
        return result

    # ── bulk access ────────────────────────────────────────────────────
    def list_all(self) -> list[dict]:
        return [dict(e) for e in _SPECIES_DB]

    def search(self, keyword: str) -> list[dict]:
        kw = keyword.strip().lower()
        results = []
        for entry in _SPECIES_DB:
            if (
                kw in entry["chinese"].lower()
                or kw in entry["english"].lower()
                or kw in entry["latin"].lower()
            ):
                results.append(dict(entry))
        return results

    def list_animals(self) -> list[dict]:
        """Return only non-human animal entries (not microbes)."""
        microbe_ids = {"1282", "1280", "1747", "76775", "554073", "287", "1314", "1270"}
        return [dict(e) for e in _SPECIES_DB if e["taxon_id"] not in microbe_ids]
