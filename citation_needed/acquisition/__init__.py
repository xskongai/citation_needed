from .acquirer import acquire_source
from .http import (
    AcquisitionNetworkError,
    ContentTooLargeError,
    HttpClient,
    HttpResponse,
    UrllibHttpClient,
)
from .providers import crossref_url, normalize_doi, unpaywall_url

__all__ = [
    "acquire_source",
    "AcquisitionNetworkError",
    "ContentTooLargeError",
    "HttpClient",
    "HttpResponse",
    "UrllibHttpClient",
    "crossref_url",
    "normalize_doi",
    "unpaywall_url",
]
