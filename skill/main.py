"""Main entry point — non-human skin microbiome literature pipeline.

Flow: user input → species normalization → PubMed search (non-human skin)
      → BioProject resolution → Excel export.
"""

import sys
import platform
from pathlib import Path

import yaml

from .species import SpeciesManager
from .search import SearchEngine
from .ena import ENAClient
from .export import Exporter

_NA = "N/A"
_BANNER = "=" * 62


def detect_platform() -> str:
    """Return 'linux', 'windows', or 'macos'."""
    s = platform.system().lower()
    if s == "linux":
        return "linux"
    elif s == "windows":
        return "windows"
    elif s == "darwin":
        return "macos"
    return s


class SkinMicrobiomeSkill:
    """Orchestrates: species → PubMed (non-human skin) → BioProject → Excel."""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.species_manager = SpeciesManager(self.config)
        self.search_engine = SearchEngine(self.config)
        self.ena_client = ENAClient(self.config)
        self.exporter = Exporter(self.config)
        self.platform = detect_platform()

    # ── config ─────────────────────────────────────────────────────────
    def _load_config(self, config_path: str) -> dict:
        p = Path(config_path)
        if not p.exists():
            print(f"[WARN] Config not found at {config_path}, using defaults.")
            return {}
        with open(p, "r") as f:
            return yaml.safe_load(f)

    # ═══════════════════════════════════════════════════════════════════
    #  Interactive pipeline
    # ═══════════════════════════════════════════════════════════════════
    def run_interactive(self) -> list[dict]:
        """Full interactive session with preview and keyword refinement."""

        print(_BANNER)
        print("  Non-Human Skin Microbiome Literature Search")
        print(f"  Platform: {self.platform}")
        print(_BANNER)

        # ── 1. Species input & normalization ──────────────────────────
        species_info = self._prompt_species()
        if species_info is None:
            return []

        species_latin = species_info.get("latin", "")
        print(f"\n  Normalized: {species_info.get('chinese', '?')}"
              f" → {species_info.get('english', '?')}"
              f" → {species_latin}")

        # ── 2. Keywords ───────────────────────────────────────────────
        keywords = input("\n  Extra keywords (optional, Enter to skip): ").strip()

        # ── 3. PubMed search ──────────────────────────────────────────
        max_n = self.search_engine.max_results
        print(f"\n  Searching PubMed (max {max_n})…")
        print(f"  Query: (skin microbiome) AND ({species_latin}) NOT human")

        articles = self.search_engine.search(
            species_latin=species_latin,
            extra_keywords=keywords,
        )
        print(f"  → {len(articles)} articles after non-human skin filter.")

        if not articles:
            print("  No results. Try broader or different species.")
            return []

        # ── 4. Preview & refine ───────────────────────────────────────
        self._preview_articles(articles)
        articles = self._refine_loop(articles, species_latin)

        # ── 5. BioProject lookup ──────────────────────────────────────
        self._resolve_bioprojects(articles)

        # ── 6. Annotate species ───────────────────────────────────────
        for art in articles:
            art["species"] = species_latin

        # ── 7. Export ─────────────────────────────────────────────────
        self._export_interactive(articles, species_latin)

        return articles

    # ── step 1: species prompt ─────────────────────────────────────────
    def _prompt_species(self) -> dict | None:
        """Ask for species name, normalize, allow retry."""
        while True:
            raw = input("\n  Species name (Chinese or English, e.g. 马 / mouse): ").strip()
            if not raw:
                print("  Please enter a species name.")
                continue

            result = self.species_manager.normalize(raw)
            if result:
                return result

            print(f"  '{raw}' not in database.")
            print("  Available animals:")
            for s in self.species_manager.list_animals():
                print(f"    {s['chinese']:8s} → {s['latin']}")
            again = input("  Try again? [Y/n]: ").strip().lower()
            if again == "n":
                return None

    # ── step 4: preview ────────────────────────────────────────────────
    def _preview_articles(self, articles: list[dict], top_n: int = 10):
        n = min(top_n, len(articles))
        print(f"\n{'─' * 80}")
        print(f"  Preview — top {n} of {len(articles)} articles")
        print(f"{'─' * 80}")
        for i, art in enumerate(articles[:n], 1):
            title = (art.get("title") or "")[:90]
            year = art.get("year", "?")
            site = art.get("sampling_site", "N/A")
            bp = art.get("bioproject_ids", [])
            bp_str = bp[0] if bp else "—"
            print(f"  [{i:2d}] {title}")
            print(f"       year={year}  site={site}  bioproject={bp_str}")
        print(f"{'─' * 80}")

    # ── step 4b: keyword refinement ────────────────────────────────────
    def _refine_loop(self, articles: list[dict], species_latin: str) -> list[dict]:
        while True:
            print("\n  Options: [Enter] continue  [r] refine keywords  [q] quit")
            choice = input("  > ").strip().lower()
            if choice == "":
                return articles
            elif choice == "q":
                sys.exit(0)
            elif choice == "r":
                new_kw = input("  Extra keywords: ").strip()
                articles = self.search_engine.search(
                    species_latin=species_latin,
                    extra_keywords=new_kw,
                )
                print(f"  → {len(articles)} articles after filter.")
                if articles:
                    self._preview_articles(articles)
                else:
                    print("  No results with these keywords.")
            else:
                print("  Unknown option.")

    # ── step 5: BioProject resolution ──────────────────────────────────
    def _resolve_bioprojects(self, articles: list[dict]):
        """Resolve BioProject IDs for each article via ENA."""
        print("\n  Resolving metagenomic BioProject IDs…")
        for art in articles:
            bp_ids = art.get("bioproject_ids", [])
            if bp_ids:
                art["bioproject_resolved"] = {
                    pid: self.ena_client.resolve_bioproject(pid)
                    for pid in bp_ids
                }
            else:
                art["bioproject_resolved"] = {}
        resolved = sum(1 for a in articles if a.get("bioproject_ids"))
        print(f"  BioProjects found in {resolved}/{len(articles)} articles.")

    # ── step 7: export ─────────────────────────────────────────────────
    def _export_interactive(self, articles: list[dict], species_name: str):
        print("\n  Export format:")
        print("    [1] Excel (.xlsx) — default")
        print("    [2] CSV")
        print("    [3] JSON")
        print("    [4] Skip")
        choice = input("  > ").strip()
        fmt_map = {"1": "xlsx", "2": "csv", "3": "json", "4": None}
        fmt = fmt_map.get(choice, "xlsx")
        if fmt is None:
            return
        path = self.exporter.export(articles, format=fmt, species_name=species_name)
        if path:
            print(f"\n  Exported to: {path}")

    # ═══════════════════════════════════════════════════════════════════
    #  Programmatic API (non-interactive)
    # ═══════════════════════════════════════════════════════════════════
    def search(self, species_latin: str, extra_keywords: str = "") -> list[dict]:
        return self.search_engine.search(species_latin=species_latin, extra_keywords=extra_keywords)

    def get_species_info(self, species_name: str) -> dict:
        return self.species_manager.get_info(species_name)

    def query_ena(self, accession: str) -> dict | None:
        return self.ena_client.query(accession)

    def export(self, data: list[dict], format: str = "xlsx",
               output_path: str = None) -> str | None:
        return self.exporter.export(data, format=format, output_path=output_path)

    def run_pipeline(
        self,
        species: str,
        extra_keywords: str = "",
        max_results: int = None,
        export_format: str = "xlsx",
    ) -> list[dict]:
        """Non-interactive pipeline for scripting / batch use.

        Returns annotated article list.
        """
        species_info = self.species_manager.normalize(species)
        if species_info is None:
            raise ValueError(f"Unknown species: {species}")
        species_latin = species_info["latin"]

        articles = self.search_engine.search(
            species_latin=species_latin,
            extra_keywords=extra_keywords,
            max_results=max_results,
        )

        for art in articles:
            art["species"] = species_latin

        if export_format:
            self.exporter.export(articles, format=export_format, species_name=species_latin)

        return articles


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════
def main():
    skill = SkinMicrobiomeSkill()

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "list-species":
            print("Non-human animals:")
            for s in skill.species_manager.list_animals():
                print(f"  {s['chinese']:8s} → {s['latin']}")
            print("\nMicrobes:")
            for s in skill.species_manager.list_all():
                if s not in skill.species_manager.list_animals():
                    print(f"  {s['chinese']:8s} → {s['latin']}")
        elif cmd == "search":
            species = sys.argv[2] if len(sys.argv) > 2 else None
            if not species:
                print("Usage: skin-microbiome search <species> [extra_keywords]")
                return
            extra = " ".join(sys.argv[3:])
            articles = skill.search(species, extra)
            for art in articles[:20]:
                print(f"  [{art.get('year', '?')}] {art.get('title', '')[:100]}")
                print(f"       site={art.get('sampling_site', 'N/A')}  "
                      f"bioproject={art.get('bioproject_ids', [])}")
        else:
            print(f"Unknown command: {cmd}")
            print("Commands: list-species, search <species> [keywords]")
        return

    skill.run_interactive()


if __name__ == "__main__":
    main()
