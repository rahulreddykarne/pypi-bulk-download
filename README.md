<div align="center">

# pypi-bulk-download

**Bulk-download PyPI packages by popularity — in parallel, with safe unpacking and a JSON manifest.**

[![PyPI](https://img.shields.io/pypi/v/pypi-bulk-download?color=blue)](https://pypi.org/project/pypi-bulk-download/)
[![Python](https://img.shields.io/pypi/pyversions/pypi-bulk-download)](https://pypi.org/project/pypi-bulk-download/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Downloads](https://static.pepy.tech/badge/pypi-bulk-download/month)](https://pepy.tech/project/pypi-bulk-download)

</div>

---

Download PyPI packages **in bulk**, filtered by real-world popularity, in
parallel, with **safe archive unpacking** and a JSON manifest. Built for
assembling research corpora (security scanning, ecosystem analysis, mirrors)
without hand-rolling `pip download` loops.

Downloads go through `pip download`, so wheels, sdists, platform tags, and
custom indexes behave exactly as pip does. Popularity comes from the public
[top-pypi-packages](https://hugovk.github.io/top-pypi-packages/) 30-day dataset.

## Highlights

- Filter by real 30-day download counts from the top-pypi-packages dataset
- Parallel downloads via `pip download` — wheels, sdists and custom indexes just work
- Tar-slip / zip-slip safe archive unpacking
- JSON manifest of every result, plus a `--dry-run` planning mode

## Install

```bash
pip install pypi-bulk-download
```

## CLI

```bash
# Top 50 packages with >= 100k downloads/month, source dists, no deps
pypi-bulk-download --min-downloads 100000 --limit 50 --format sdist --no-deps -o corpus/

# Specific packages, 4 workers, write a manifest
pypi-bulk-download --packages requests flask httpx --workers 4 --save-manifest corpus/manifest.json

# From a requirements file, then safely unpack every archive
pypi-bulk-download -r requirements.txt -o corpus/ --unpack

# See the plan without downloading
pypi-bulk-download --min-downloads 50000 --limit 20 --dry-run
```

## Library

```python
from pypi_bulk_download import fetch_top_packages, download_many, save_manifest

targets = fetch_top_packages(min_downloads=100_000, limit=25)
results = download_many(targets, "corpus/", workers=4, prefer_format="sdist", no_deps=True)
save_manifest(results, "corpus/manifest.json")

print(sum(r.success for r in results), "of", len(results), "downloaded")
```

### Safe unpacking

`unpack_archive` / `unpack_all` validate every tar/zip member against path
traversal (tar-slip / zip-slip) before extracting — untrusted archives can't
write outside their destination folder.

```python
from pypi_bulk_download import unpack_all
unpacked, failed = unpack_all("corpus/", remove_archives=False)
```

## Notes

- Depends only on `requests` (plus `pip`, which you already have).
- `--format sdist` falls back to the best wheel when no source distribution
  exists, rather than failing hard.
- **This tool downloads third-party code.** Do not commit the download
  directory to your own repository; the included `.gitignore` excludes `pkgs/`,
  `downloads/`, and archive files by default.

## Development

```bash
git clone https://github.com/rahulreddykarne/pypi-bulk-download.git
cd pypi-bulk-download
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
python -m build
```

Bug reports and pull requests are welcome on the [issue tracker](https://github.com/rahulreddykarne/pypi-bulk-download/issues).

## Related projects

Part of a small toolkit for Python supply-chain security research:

| Project | What it does |
| --- | --- |
| [tarslip-guard](https://github.com/rahulreddykarne/tarslip-guard) | Detect unsafe extractall() calls and safely extract tar/zip archives. |
| [pypi-version-bisect](https://github.com/rahulreddykarne/pypi-version-bisect) | Find a vulnerability's affected version range in O(log n) checks. |
| [pypi-blast-radius](https://github.com/rahulreddykarne/pypi-blast-radius) | Estimate the downstream impact of a PyPI package version. |
| [osv-dedupe](https://github.com/rahulreddykarne/osv-dedupe) | Score security findings against published OSV/NVD advisories. |
| [installtime-audit](https://github.com/rahulreddykarne/installtime-audit) | Flag install-time side effects in setup.py and friends. |
| [cvss-estimator](https://github.com/rahulreddykarne/cvss-estimator) | CVSS v3.1 calculator and evidence-driven vector estimator. |

## License

Released under the [MIT License](LICENSE).
