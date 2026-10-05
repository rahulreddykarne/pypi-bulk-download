"""pypi-bulk-download: download PyPI packages in bulk, filtered by popularity.

Public API
----------
- :func:`fetch_top_packages` – (name, downloads) pairs from the top-packages dataset.
- :func:`download_package`, :func:`download_many` – download via ``pip download``.
- :func:`save_manifest` – write a JSON manifest of results.
- :func:`load_requirements`, :func:`base_package_name` – input helpers.
- :func:`unpack_archive`, :func:`unpack_all` – safe (traversal-checked) unpacking.
- :class:`DownloadResult`.
"""

from __future__ import annotations

from ._archive import unpack_all, unpack_archive
from ._core import (
    DownloadResult,
    base_package_name,
    download_many,
    download_package,
    fetch_top_packages,
    load_requirements,
    save_manifest,
)

__all__ = [
    "DownloadResult",
    "fetch_top_packages",
    "download_package",
    "download_many",
    "save_manifest",
    "load_requirements",
    "base_package_name",
    "unpack_archive",
    "unpack_all",
]
__version__ = "0.1.0"
