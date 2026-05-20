"""ENA BioProject metagenomic dataset retrieval."""

import json
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

_ENA_BROWSER = "https://www.ebi.ac.uk/ena/browser/api"


def _ena_get(endpoint: str) -> dict | list | None:
    """GET request to ENA Browser API, return parsed JSON or None."""
    url = f"{_ENA_BROWSER}/{endpoint}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError) as e:
        print(f"[WARN] ENA API request failed: {url} — {e}")
        return None


class ENAClient:
    """Resolve BioProject (PRJNAxxx / PRJEBxxx) metagenomic datasets."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        ena_cfg = self.config.get("ena", {})
        self.base_url = ena_cfg.get("base_url", _ENA_BROWSER)

    # ── metagenomic dataset resolution ─────────────────────────────────
    def resolve_bioproject(self, bioproject_id: str) -> str:
        """Resolve a BioProject ID to a human-readable description.

        Returns description string, or 'N/A' if unreachable.
        """
        data = _ena_get(f"summary/{bioproject_id}")
        if not data:
            return "N/A"
        try:
            if isinstance(data, dict):
                title = (
                    data.get("title")
                    or data.get("description")
                    or data.get("study_alias")
                    or str(data)
                )
                return str(title)
            return str(data)
        except Exception:
            return "N/A"

    def get_bioproject_summary(self, bioproject_id: str) -> dict:
        """Get full summary JSON for a BioProject.

        Returns dict with metadata, or {"error": "N/A"}.
        """
        data = _ena_get(f"summary/{bioproject_id}")
        if data is None:
            return {"error": "N/A"}
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and len(data) > 0:
            return data[0] if isinstance(data[0], dict) else {"raw": data}
        return {"raw": data}

    def batch_resolve_bioprojects(self, bioproject_ids: list[str]) -> dict[str, str]:
        """Resolve multiple BioProject IDs. Returns {id: description}."""
        results = {}
        for pid in bioproject_ids:
            results[pid] = self.resolve_bioproject(pid)
            time.sleep(0.2)
        return results

    # ── legacy methods ─────────────────────────────────────────────────
    def query(self, accession: str) -> dict | None:
        return _ena_get(f"summary/{accession}")

    def get_study(self, study_accession: str) -> dict | None:
        return _ena_get(f"summary/{study_accession}")

    def get_sample(self, sample_accession: str) -> dict | None:
        return _ena_get(f"summary/{sample_accession}")

    def get_run(self, run_accession: str) -> dict | None:
        return _ena_get(f"summary/{run_accession}")

    def get_sequence(self, accession: str) -> str | None:
        url = f"{_ENA_BROWSER}/sequence/{accession}"
        req = Request(url, headers={"Accept": "text/x-fasta"})
        try:
            with urlopen(req, timeout=60) as resp:
                return resp.read().decode()
        except (HTTPError, URLError) as e:
            print(f"[WARN] ENA sequence fetch failed: {url} — {e}")
            return None

    def batch_query(self, accessions: list[str]) -> dict[str, dict]:
        results = {}
        for acc in accessions:
            data = self.query(acc)
            if data:
                results[acc] = data
            time.sleep(0.2)
        return results
