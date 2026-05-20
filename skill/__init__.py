"""skin_microbiome_skill — non-human skin microbiome literature search.

Patterns adopted from bioSkills database-access:
  - entrez-search: field-tag query syntax, pagination, history server
  - entrez-fetch: ESummary + EFetch for records
  - entrez-link: cross-database navigation (PubMed → BioProject / SRA)
  - sra-data: SRA accession hierarchy
"""

from .main import SkinMicrobiomeSkill, detect_platform
from .species import SpeciesManager
from .search import SearchEngine
from .ena import ENAClient
from .export import Exporter

__version__ = "0.3.0"
__all__ = [
    "SkinMicrobiomeSkill",
    "SpeciesManager",
    "SearchEngine",
    "ENAClient",
    "Exporter",
    "detect_platform",
]
