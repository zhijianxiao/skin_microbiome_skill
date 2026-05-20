"""ENA / NCBI BioProject metagenomic dataset resolution.

Patterns adopted from bioSkills database-access:
  - entrez-fetch:  ESummary for BioProject metadata
  - entrez-link:   Navigate BioProject → SRA runs
  - sra-data:      SRA accession hierarchy (SRP > SRX > SRS > SRR)
"""

import json
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

from Bio import Entrez

_ENA_BROWSER = "https://www.ebi.ac.uk/ena/browser/api"

def _ena_get(endpoint: str) -> dict | list | None:
    url = f"{_ENA_BROWSER}/{endpoint}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except (HTTPError, URLError) as e:
        print(f"[WARN] ENA API failed: {url} — {e}")
        return None


class ENAClient:
    """Resolve BioProject and SRA metagenomic datasets via NCBI Entrez + ENA.

    Patterns from bioSkills:
      - entrez-fetch/ESummary for BioProject metadata
      - entrez-link for BioProject → SRA run navigation
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        sc = self.config.get("search", {})
        Entrez.email = sc.get("email", "user@example.com")
        if sc.get("api_key"):
            Entrez.api_key = sc["api_key"]
        ec = self.config.get("ena", {})
        self.base_url = ec.get("base_url", _ENA_BROWSER)

    # ── BioProject resolution (Entrez path — bioSkills pattern) ────────
    def resolve_bioproject(self, bioproject_id: str) -> str:
        """Get BioProject title/description via Entrez ESummary.

        Pattern from bioSkills entrez-fetch: ESummary for quick metadata.
        """
        try:
            handle = Entrez.esummary(db="bioproject", id=bioproject_id)
            summary = Entrez.read(handle)
            handle.close()
            s = summary[0] if isinstance(summary, list) else summary
            return str(
                s.get("title")
                or s.get("Project_Title")
                or s.get("project_title", "N/A")
            )
        except Exception:
            # Fallback to ENA API
            data = _ena_get(f"summary/{bioproject_id}")
            if data:
                try:
                    if isinstance(data, dict):
                        return str(data.get("title") or data.get("description", "N/A"))
                    return str(data)
                except Exception:
                    pass
        return "N/A"

    def get_bioproject_summary(self, bioproject_id: str) -> dict:
        """Full BioProject summary via Entrez ESummary."""
        try:
            handle = Entrez.esummary(db="bioproject", id=bioproject_id)
            record = Entrez.read(handle)
            handle.close()
            if isinstance(record, list) and len(record) > 0:
                return dict(record[0])
        except Exception:
            data = _ena_get(f"summary/{bioproject_id}")
            if isinstance(data, dict):
                return data
            if isinstance(data, list) and len(data) > 0:
                return data[0] if isinstance(data[0], dict) else {"raw": data}
        return {"error": "N/A"}

    # ── BioProject → SRA runs (entrez-link pattern) ────────────────────
    def get_sra_runs_for_bioproject(self, bioproject_id: str, max_runs: int = 20) -> list[str]:
        """Find SRA run accessions (SRR) linked to a BioProject.

        Pattern from bioSkills:
          entrez-link: BioProject → SRA
          sra-data: accession hierarchy
        """
        try:
            handle = Entrez.elink(dbfrom="bioproject", db="sra", id=bioproject_id)
            record = Entrez.read(handle)
            handle.close()

            sra_ids = []
            for linkset in record:
                for db in linkset.get("LinkSetDb", []):
                    sra_ids.extend(link["Id"] for link in db.get("Link", []))

            if not sra_ids:
                return []

            # Fetch run info to get SRR IDs (sra-data pattern)
            run_ids = []
            for uid in sra_ids[:max_runs]:
                try:
                    handle = Entrez.efetch(
                        db="sra", id=uid,
                        rettype="runinfo", retmode="text",
                    )
                    runinfo = handle.read().decode()
                    handle.close()
                    for line in runinfo.strip().split("\n")[1:]:
                        if line:
                            run_ids.append(line.split(",")[0])
                except Exception:
                    pass
                time.sleep(0.3)
            return run_ids
        except Exception as e:
            print(f"[WARN] SRA run fetch failed for {bioproject_id}: {e}")
            return []

    def batch_resolve_bioprojects(self, bioproject_ids: list[str]) -> dict[str, str]:
        results = {}
        for pid in bioproject_ids:
            results[pid] = self.resolve_bioproject(pid)
            time.sleep(0.2)
        return results

    # ── legacy ENA API methods ─────────────────────────────────────────
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
