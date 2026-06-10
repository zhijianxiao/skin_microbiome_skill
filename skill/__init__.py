"""skinmicrobiome — non-human skin microbiome literature search.

Boolean keyword query + relevance scoring + NCBI Taxonomy term expansion.
"""

from .main import SkinMicrobiomeSkill, detect_platform
from .species import SpeciesManager
from .search import SearchEngine
from .ena import ENAClient
from .export import Exporter

__version__ = "0.4.0"
__all__ = [
    "SkinMicrobiomeSkill",
    "SpeciesManager",
    "SearchEngine",
    "ENAClient",
    "Exporter",
    "detect_platform",
]
