"""Bulk-download PyPI packages, optionally filtered by popularity.

Downloads are performed with ``pip download`` (so wheels, sdists, platform tags,
and index URLs behave exactly as pip does). Popularity data comes from the
public `top-pypi-packages <https://hugovk.github.io/top-pypi-packages/>`_
dataset (30-day download counts).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_TOP_PACKAGES_URL = "https://hugovk.github.io/top-pypi-packages/top-pypi-packages.min.json"
_PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*")
_TOP_CACHE: list[tuple[str, int]] = []


@dataclass
class DownloadResult:
    package: str
    success: bool
    path: Optional[str] = None
    error: Optional[str] = None
    downloads_last_month: int = 0
    elapsed: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Popularity dataset
# --------------------------------------------------------------------------- #
def fetch_top_packages(
    min_downloads: int = 0,
    limit: Optional[int] = None,
    *,
    timeout: float = 30.0,
) -> list[tuple[str, int]]:
    """Return ``(name, downloads_last_month)`` pairs from the top-packages dataset.

    Sorted by download count descending. Filtered to ``>= min_downloads`` and
    truncated to *limit* if given. The dataset is fetched once and cached in
    process.
    """
    global _TOP_CACHE
    if not _TOP_CACHE:
        resp = requests.get(_TOP_PACKAGES_URL, timeout=timeout)
        resp.raise_for_status()
        rows = resp.json().get("rows") or []
        _TOP_CACHE = [
            (str(row.get("project") or ""), int(row.get("download_count") or 0))
            for row in rows
            if row.get("project")
        ]
        _TOP_CACHE.sort(key=lambda item: item[1], reverse=True)
    result = [(name, dl) for name, dl in _TOP_CACHE if dl >= min_downloads]
    return result[:limit] if limit else result


# --------------------------------------------------------------------------- #
# Requirements / name parsing
# --------------------------------------------------------------------------- #
def base_package_name(package_spec: str) -> str:
    """Return the PyPI project name from a requirement/specifier string."""
    text = package_spec.strip()
    if not text:
        return text
    text = text.split(";", 1)[0].strip()
    if " @ " in text:
        text = text.split(" @ ", 1)[0].strip()
    text = text.split("[", 1)[0].strip()
    match = _PACKAGE_NAME_RE.match(text)
    return match.group(0) if match else text


def load_requirements(path: str) -> list[str]:
    """Parse a requirements.txt into a list of requirement lines (no options)."""
    packages: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if " #" in line:
                line = line[: line.index(" #")].strip()
            packages.append(line)
    return packages


# --------------------------------------------------------------------------- #
# pip download
# --------------------------------------------------------------------------- #
def _build_pip_cmd(
    package: str,
    output_dir: str,
    *,
    no_deps: bool,
    python_version: Optional[str],
    platform: Optional[str],
    index_url: Optional[str],
    extra_index_url: Optional[str],
    prefer_format: str,
    pre: bool,
) -> list[str]:
    cmd = [sys.executable, "-m", "pip", "download", package, "-d", output_dir, "--quiet"]
    if no_deps:
        cmd.append("--no-deps")
    if python_version:
        cmd += ["--python-version", python_version]
    if platform:
        cmd += ["--platform", platform, "--only-binary", ":all:"]
    if index_url:
        cmd += ["--index-url", index_url]
    if extra_index_url:
        cmd += ["--extra-index-url", extra_index_url]
    if prefer_format == "wheel":
        cmd += ["--only-binary", ":all:"]
    elif prefer_format == "sdist":
        cmd += ["--no-binary", ":all:"]
    if pre:
        cmd.append("--pre")
    return cmd


def _run_pip_download(package: str, output_dir: str, *, prefer_format: str, pip_timeout: int, **kw) -> tuple[bool, str, float]:
    cmd = _build_pip_cmd(package, output_dir, prefer_format=prefer_format, **kw)
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=pip_timeout)
        elapsed = time.monotonic() - t0
        if proc.returncode == 0:
            return True, "", elapsed
        err = (proc.stderr or proc.stdout or "").strip()
        return False, err[:500], elapsed
    except subprocess.TimeoutExpired:
        return False, f"pip download timed out after {pip_timeout}s", time.monotonic() - t0
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), time.monotonic() - t0


def download_package(
    package: str,
    output_dir: str,
    *,
    no_deps: bool = False,
    python_version: Optional[str] = None,
    platform: Optional[str] = None,
    index_url: Optional[str] = None,
    extra_index_url: Optional[str] = None,
    prefer_format: str = "any",
    pre: bool = False,
    pip_timeout: int = 120,
    downloads_last_month: int = 0,
) -> DownloadResult:
    """Download a single package with ``pip download``.

    When *prefer_format* is ``"sdist"`` and no source distribution is available,
    falls back to the best wheel instead of a hard failure.
    """
    os.makedirs(output_dir, exist_ok=True)
    common = dict(
        no_deps=no_deps,
        python_version=python_version,
        platform=platform,
        index_url=index_url,
        extra_index_url=extra_index_url,
        pre=pre,
    )
    ok, err, elapsed = _run_pip_download(package, output_dir, prefer_format=prefer_format, pip_timeout=pip_timeout, **common)

    if not ok and prefer_format == "sdist":
        logger.info("  %s: sdist unavailable/failed, falling back to wheel...", package)
        fb_ok, fb_err, fb_elapsed = _run_pip_download(
            package, output_dir, prefer_format="wheel", pip_timeout=pip_timeout, **common
        )
        elapsed += fb_elapsed
        if fb_ok:
            ok, err = True, ""
        else:
            err = f"sdist failed ({err}); wheel fallback failed ({fb_err})"[:500]

    if ok:
        return DownloadResult(package, True, path=output_dir, downloads_last_month=downloads_last_month, elapsed=elapsed)
    return DownloadResult(package, False, error=err, downloads_last_month=downloads_last_month, elapsed=elapsed)


def download_many(
    packages,
    output_dir: str,
    *,
    workers: int = 1,
    **download_kwargs,
) -> list[DownloadResult]:
    """Download many packages, optionally in parallel.

    *packages* is an iterable of names or ``(name, downloads_last_month)`` pairs.
    Extra keyword args are forwarded to :func:`download_package`.
    """
    items = [(p if isinstance(p, tuple) else (p, 0)) for p in packages]
    results: list[DownloadResult] = []

    if workers <= 1:
        for name, dl in items:
            results.append(download_package(name, output_dir, downloads_last_month=dl, **download_kwargs))
        return results

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_package, name, output_dir, downloads_last_month=dl, **download_kwargs): name
            for name, dl in items
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: (-int(r.downloads_last_month or 0), r.package.lower()))
    return results


def save_manifest(results: list[DownloadResult], path: str) -> None:
    """Write a JSON manifest of download results."""
    payload = {
        "generated_by": "pypi-bulk-download",
        "count": len(results),
        "succeeded": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [r.to_dict() for r in results],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
