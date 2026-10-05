"""Command-line interface for pypi-bulk-download."""

from __future__ import annotations

import argparse
import logging
import sys

from ._archive import unpack_all
from ._core import (
    download_many,
    fetch_top_packages,
    load_requirements,
    save_manifest,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pypi-bulk-download",
        description="Bulk-download PyPI packages, optionally filtered by popularity.",
    )
    src = parser.add_argument_group("package selection")
    src.add_argument("--packages", nargs="+", metavar="NAME", help="explicit package names")
    src.add_argument("-r", "--requirements", metavar="FILE", help="download from a requirements file")
    src.add_argument("--min-downloads", type=int, default=0, help="filter top-packages by monthly downloads")
    src.add_argument("--limit", type=int, default=None, help="cap the number of packages")

    out = parser.add_argument_group("output")
    out.add_argument("-o", "--output-dir", default="pkgs", help="destination directory (default: pkgs)")
    out.add_argument("--format", choices=["any", "wheel", "sdist"], default="any", help="preferred distribution format")
    out.add_argument("--no-deps", action="store_true", help="do not download dependencies")
    out.add_argument("--python-version", help="target Python version, e.g. 3.11")
    out.add_argument("--platform", help="target platform tag (implies wheels only)")
    out.add_argument("--pre", action="store_true", help="include pre-releases")
    out.add_argument("--workers", type=int, default=1, help="parallel download workers")
    out.add_argument("--pip-timeout", type=int, default=120, help="per-package pip timeout (s)")
    out.add_argument("--save-manifest", metavar="FILE", help="write a JSON manifest of results")
    out.add_argument("--unpack", action="store_true", help="safely unpack archives after download")
    out.add_argument("--dry-run", action="store_true", help="print the plan without downloading")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _select_packages(args) -> list:
    if args.packages:
        return list(args.packages)
    if args.requirements:
        return load_requirements(args.requirements)
    if args.min_downloads > 0 or args.limit:
        return fetch_top_packages(min_downloads=args.min_downloads, limit=args.limit)
    return []


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    packages = _select_packages(args)
    if not packages:
        print("Nothing to download. Use --packages, -r, or --min-downloads/--limit.", file=sys.stderr)
        return 2

    if args.dry_run:
        for item in packages:
            name, dl = item if isinstance(item, tuple) else (item, 0)
            print(f"{name}  ({dl:,} downloads/mo)" if dl else name)
        print(f"\n{len(packages)} package(s) would be downloaded to {args.output_dir}/")
        return 0

    results = download_many(
        packages,
        args.output_dir,
        workers=args.workers,
        no_deps=args.no_deps,
        python_version=args.python_version,
        platform=args.platform,
        prefer_format=args.format,
        pre=args.pre,
        pip_timeout=args.pip_timeout,
    )

    succeeded = sum(1 for r in results if r.success)
    for r in results:
        status = "ok " if r.success else "FAIL"
        detail = "" if r.success else f"  ({r.error})"
        print(f"[{status}] {r.package}{detail}")
    print(f"\n{succeeded}/{len(results)} downloaded to {args.output_dir}/", file=sys.stderr)

    if args.unpack:
        unpacked, failed = unpack_all(args.output_dir)
        print(f"unpacked {unpacked} archive(s), {failed} failed", file=sys.stderr)

    if args.save_manifest:
        save_manifest(results, args.save_manifest)
        print(f"manifest written to {args.save_manifest}", file=sys.stderr)

    return 0 if succeeded == len(results) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
