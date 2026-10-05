import io
import json
import tarfile

import pytest

import pypi_bulk_download._core as core
from pypi_bulk_download import (
    DownloadResult,
    base_package_name,
    fetch_top_packages,
    load_requirements,
    save_manifest,
    unpack_archive,
)


def test_base_package_name():
    assert base_package_name("requests==2.31.0") == "requests"
    assert base_package_name("flask[async]>=2 ; python_version>'3.8'") == "flask"
    assert base_package_name("mypkg @ https://example/x.whl") == "mypkg"


def test_load_requirements(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(
        "# comment\nrequests==2.31.0\n-r other.txt\nflask  # inline\n\n--extra-index-url http://x\n"
    )
    assert load_requirements(str(req)) == ["requests==2.31.0", "flask"]


def test_fetch_top_packages(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"rows": [
                {"project": "boto3", "download_count": 900},
                {"project": "requests", "download_count": 500},
                {"project": "rare", "download_count": 10},
            ]}

    core._TOP_CACHE.clear()
    monkeypatch.setattr(core.requests, "get", lambda *a, **k: _Resp())
    top = fetch_top_packages(min_downloads=100, limit=2)
    assert top == [("boto3", 900), ("requests", 500)]
    core._TOP_CACHE.clear()


def test_save_manifest(tmp_path):
    results = [
        DownloadResult("a", True, path="out", downloads_last_month=5),
        DownloadResult("b", False, error="boom"),
    ]
    manifest = tmp_path / "m.json"
    save_manifest(results, str(manifest))
    data = json.loads(manifest.read_text())
    assert data["count"] == 2
    assert data["succeeded"] == 1
    assert data["failed"] == 1


def test_unpack_archive_safe(tmp_path):
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        payload = b"hi"
        info = tarfile.TarInfo("pkg/file.txt")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
    dest = tmp_path / "out"
    assert unpack_archive(str(archive), str(dest)) == str(dest)
    assert (dest / "pkg" / "file.txt").read_bytes() == b"hi"


def test_unpack_archive_rejects_traversal(tmp_path):
    archive = tmp_path / "evil.tar"
    with tarfile.open(archive, "w") as tf:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 0
        tf.addfile(info, io.BytesIO(b""))
    dest = tmp_path / "out"
    # unpack_archive swallows the ValueError and returns None (logged failure).
    assert unpack_archive(str(archive), str(dest)) is None
    assert not (tmp_path / "escape.txt").exists()
