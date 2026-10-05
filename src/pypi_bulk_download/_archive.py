"""Safe archive unpacking (rejects tar-slip / zip-slip path traversal)."""

from __future__ import annotations

import logging
import os
import tarfile
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)

_ARCHIVE_EXTS = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip", ".whl", ".egg")


def is_archive(path: str) -> bool:
    return any(path.lower().endswith(ext) for ext in _ARCHIVE_EXTS)


def _safe_member_path(dest_dir: str, member_name: str) -> str:
    if not member_name:
        raise ValueError("archive contains an empty member name")
    base = os.path.realpath(dest_dir)
    target = os.path.realpath(os.path.join(dest_dir, member_name))
    try:
        if os.path.commonpath([base, target]) != base:
            raise ValueError
    except ValueError as exc:
        raise ValueError(f"unsafe archive member path: {member_name!r}") from exc
    return target


def _safe_tar_members(tf: tarfile.TarFile, dest_dir: str) -> list[tarfile.TarInfo]:
    members: list[tarfile.TarInfo] = []
    for member in tf.getmembers():
        _safe_member_path(dest_dir, member.name)
        if not (member.isfile() or member.isdir()):
            logger.warning("  Skipping unsupported tar member: %s", member.name)
            continue
        members.append(member)
    return members


def _validate_zip_members(zf: zipfile.ZipFile, dest_dir: str) -> None:
    for member in zf.infolist():
        _safe_member_path(dest_dir, member.filename)


def unpack_archive(archive_path: str, dest_dir: str) -> Optional[str]:
    """Extract *archive_path* into *dest_dir*, returning the folder or None on error."""
    os.makedirs(dest_dir, exist_ok=True)
    try:
        if archive_path.endswith((".zip", ".whl", ".egg")):
            with zipfile.ZipFile(archive_path, "r") as zf:
                _validate_zip_members(zf, dest_dir)
                zf.extractall(dest_dir)  # noqa: S202 - members validated above
        elif any(archive_path.endswith(ext) for ext in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(dest_dir, members=_safe_tar_members(tf, dest_dir))  # noqa: S202
        else:
            logger.warning("Unsupported archive format: %s", archive_path)
            return None
        logger.debug("  Unpacked: %s -> %s", os.path.basename(archive_path), dest_dir)
        return dest_dir
    except Exception as exc:  # noqa: BLE001
        logger.warning("  Failed to unpack %s: %s", os.path.basename(archive_path), exc)
        return None


def unpack_all(output_dir: str, remove_archives: bool = False) -> tuple[int, int]:
    """Unpack every archive in *output_dir* into a same-named subfolder.

    Returns ``(unpacked_count, failed_count)``.
    """
    unpacked = 0
    failed = 0
    for fname in os.listdir(output_dir):
        fpath = os.path.join(output_dir, fname)
        if not (os.path.isfile(fpath) and is_archive(fpath)):
            continue
        dest = os.path.join(output_dir, fname + "_extracted")
        if unpack_archive(fpath, dest):
            unpacked += 1
            if remove_archives:
                os.remove(fpath)
        else:
            failed += 1
    return unpacked, failed
