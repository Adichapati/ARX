import asyncio
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from fastapi.responses import JSONResponse

import dashboard.app as app_module
from dashboard.services.world_service import WorldService


def _zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            zf.writestr(name, payload)
    return buf.getvalue()


def _zip_with_symlink(link_name: str, target: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo(link_name)
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        zf.writestr(info, target)
    return buf.getvalue()


class _FakeRequest:
    def __init__(self, payload: dict | None = None):
        self.session = {"user": "tester", "csrf_token": "test-csrf-token"}
        self.headers = {"x-csrf-token": "test-csrf-token"}
        self._payload = payload or {}

    async def json(self):
        return self._payload


class WorldServiceZipSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.minecraft_dir = self.root / "minecraft"
        self.backups_dir = self.minecraft_dir / "backups"
        self.minecraft_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self._patchers = [
            patch("dashboard.services.world_service.MINECRAFT_DIR", self.minecraft_dir),
            patch("dashboard.services.world_service.BACKUPS_DIR", self.backups_dir),
            patch("dashboard.services.world_service.ServerService.is_running", return_value=False),
            patch("dashboard.services.world_service.ServerService.stop"),
            patch("dashboard.services.world_service.ServerService.start"),
            patch("dashboard.services.world_service.PropertiesService.read_all", return_value={"level-name": "world"}),
        ]
        for p in self._patchers:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_backup(self, name: str, raw: bytes) -> str:
        (self.backups_dir / name).write_bytes(raw)
        return name

    def test_valid_archive_extracts_normally(self):
        raw = _zip_bytes(
            [
                ("world/level.dat", b"level"),
                ("world/region/r.0.0.mca", b"region"),
            ]
        )

        result = WorldService.upload_world_zip_bytes(raw, "valid-world.zip")

        self.assertTrue(result["ok"])
        self.assertEqual((self.minecraft_dir / "world" / "level.dat").read_bytes(), b"level")
        self.assertEqual((self.minecraft_dir / "world" / "region" / "r.0.0.mca").read_bytes(), b"region")

    def test_archive_with_traversal_entry_is_rejected(self):
        raw = _zip_bytes(
            [
                ("world/level.dat", b"level"),
                ("../outside.txt", b"owned"),
            ]
        )

        result = WorldService.upload_world_zip_bytes(raw, "traversal.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "../outside.txt")
        self.assertEqual(result["details"]["reason"], "Path traversal is not allowed")
        self.assertFalse((self.root / "outside.txt").exists())

    def test_archive_with_backslash_traversal_entry_is_rejected(self):
        raw = _zip_bytes(
            [
                ("world\\..\\outside.txt", b"owned"),
            ]
        )

        result = WorldService.upload_world_zip_bytes(raw, "traversal-backslash.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "world\\..\\outside.txt")
        self.assertEqual(result["details"]["reason"], "Path traversal is not allowed")
        self.assertFalse((self.root / "outside.txt").exists())

    def test_archive_with_absolute_path_entry_is_rejected(self):
        raw = _zip_bytes(
            [
                ("/abs/path.txt", b"owned"),
            ]
        )

        result = WorldService.upload_world_zip_bytes(raw, "absolute.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "/abs/path.txt")
        self.assertEqual(result["details"]["reason"], "Absolute paths are not allowed")

    def test_archive_with_windows_drive_path_is_rejected(self):
        raw = _zip_bytes(
            [
                ("C:/evil.txt", b"owned"),
            ]
        )

        result = WorldService.upload_world_zip_bytes(raw, "windows-drive.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "C:/evil.txt")
        self.assertEqual(result["details"]["reason"], "Drive-prefixed paths are not allowed")

    def test_archive_with_symlink_entry_is_rejected(self):
        raw = _zip_with_symlink("world-link", "../outside")

        result = WorldService.upload_world_zip_bytes(raw, "symlink.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "world-link")
        self.assertEqual(result["details"]["reason"], "Symlink entries are not allowed")

    def test_upload_invalid_zip_has_structured_reason(self):
        result = WorldService.upload_world_zip_bytes(b"this is not a zip", "invalid.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Invalid zip archive")
        self.assertEqual(result["details"]["reason"], "Bad zip file")

    def test_upload_corrupt_zip_has_structured_member_and_reason(self):
        raw = _zip_bytes([("world/level.dat", b"level")])

        with patch("dashboard.services.world_service.zipfile.ZipFile.testzip", return_value="world/level.dat"):
            result = WorldService.upload_world_zip_bytes(raw, "corrupt.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Corrupt zip member: world/level.dat")
        self.assertEqual(result["details"]["member"], "world/level.dat")
        self.assertEqual(result["details"]["reason"], "Member failed integrity check")

    def test_upload_unsafe_archive_is_rejected_before_testzip(self):
        raw = _zip_bytes(
            [
                ("../outside.txt", b"owned"),
            ]
        )

        with patch("dashboard.services.world_service.zipfile.ZipFile.testzip", side_effect=RuntimeError("testzip should not be called")):
            result = WorldService.upload_world_zip_bytes(raw, "unsafe-before-testzip.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "../outside.txt")

    def test_upload_rejected_archive_cleans_up_temp_zip(self):
        raw = _zip_bytes(
            [
                ("../outside.txt", b"owned"),
            ]
        )

        self.assertEqual(list(self.backups_dir.glob("upload-*")), [])
        result = WorldService.upload_world_zip_bytes(raw, "cleanup-unsafe.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(list(self.backups_dir.glob("upload-*")), [])

    def test_upload_archive_with_too_many_entries_is_rejected(self):
        raw = _zip_bytes(
            [
                ("world/a.txt", b"a"),
                ("world/b.txt", b"b"),
                ("world/c.txt", b"c"),
            ]
        )

        with patch.object(WorldService, "MAX_ARCHIVE_MEMBERS", 2):
            result = WorldService.upload_world_zip_bytes(raw, "too-many-entries.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "<archive>")
        self.assertIn("too many entries", result["details"]["reason"])

    def test_upload_archive_with_large_uncompressed_total_is_rejected(self):
        raw = _zip_bytes(
            [
                ("world/a.txt", b"123456"),
                ("world/b.txt", b"abcdef"),
            ]
        )

        with patch.object(WorldService, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 10):
            result = WorldService.upload_world_zip_bytes(raw, "too-large-uncompressed.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "world/b.txt")
        self.assertIn("uncompressed size exceeds limit", result["details"]["reason"])

    def test_upload_extraction_io_failure_returns_structured_error(self):
        raw = _zip_bytes([("world/level.dat", b"level")])

        with patch("dashboard.services.world_service.shutil.copyfileobj", side_effect=OSError("disk full")):
            result = WorldService.upload_world_zip_bytes(raw, "extract-fail.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Failed to extract zip archive")
        self.assertEqual(result["details"]["member"], "world/level.dat")
        self.assertIn("disk full", result["details"]["reason"])

    def test_restore_valid_archive_extracts_normally(self):
        backup_name = self._write_backup(
            "restore-valid.zip",
            _zip_bytes(
                [
                    ("world/level.dat", b"restored-level"),
                    ("world/region/r.0.0.mca", b"restored-region"),
                ]
            ),
        )

        result = WorldService.restore_backup(backup_name)

        self.assertTrue(result["ok"])
        self.assertEqual((self.minecraft_dir / "world" / "level.dat").read_bytes(), b"restored-level")
        self.assertEqual((self.minecraft_dir / "world" / "region" / "r.0.0.mca").read_bytes(), b"restored-region")

    def test_restore_archive_with_traversal_is_rejected_with_details(self):
        backup_name = self._write_backup(
            "restore-traversal.zip",
            _zip_bytes(
                [
                    ("world/level.dat", b"level"),
                    ("../outside.txt", b"owned"),
                ]
            ),
        )

        result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "../outside.txt")
        self.assertEqual(result["details"]["reason"], "Path traversal is not allowed")
        self.assertFalse((self.root / "outside.txt").exists())

    def test_restore_archive_with_backslash_traversal_is_rejected_with_details(self):
        backup_name = self._write_backup(
            "restore-traversal-backslash.zip",
            _zip_bytes(
                [
                    ("world\\..\\outside.txt", b"owned"),
                ]
            ),
        )

        result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "world\\..\\outside.txt")
        self.assertEqual(result["details"]["reason"], "Path traversal is not allowed")
        self.assertFalse((self.root / "outside.txt").exists())

    def test_restore_invalid_zip_has_structured_reason(self):
        backup_name = self._write_backup("restore-invalid.zip", b"not a zip")

        result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Invalid zip archive")
        self.assertEqual(result["details"]["reason"], "Bad zip file")

    def test_restore_corrupt_zip_has_structured_member_and_reason(self):
        backup_name = self._write_backup("restore-corrupt.zip", _zip_bytes([("world/level.dat", b"level")]))

        with patch("dashboard.services.world_service.zipfile.ZipFile.testzip", return_value="world/level.dat"):
            result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Corrupt zip member: world/level.dat")
        self.assertEqual(result["details"]["member"], "world/level.dat")
        self.assertEqual(result["details"]["reason"], "Member failed integrity check")

    def test_restore_unsafe_archive_is_rejected_before_testzip(self):
        backup_name = self._write_backup(
            "restore-unsafe-before-testzip.zip",
            _zip_bytes(
                [
                    ("../outside.txt", b"owned"),
                ]
            ),
        )

        with patch("dashboard.services.world_service.zipfile.ZipFile.testzip", side_effect=RuntimeError("testzip should not be called")):
            result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "../outside.txt")

    def test_restore_invalid_backup_name_with_backslashes_is_rejected(self):
        result = WorldService.restore_backup("folder\\backup.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Invalid backup name")

    def test_restore_invalid_backup_name_with_absolute_path_is_rejected(self):
        result = WorldService.restore_backup("/tmp/backup.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Invalid backup name")

    def test_restore_invalid_backup_name_with_drive_prefix_is_rejected(self):
        result = WorldService.restore_backup("C:\\backup.zip")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Invalid backup name")

    def test_restore_archive_with_too_many_entries_is_rejected(self):
        backup_name = self._write_backup(
            "restore-too-many-entries.zip",
            _zip_bytes(
                [
                    ("world/a.txt", b"a"),
                    ("world/b.txt", b"b"),
                    ("world/c.txt", b"c"),
                ]
            ),
        )

        with patch.object(WorldService, "MAX_ARCHIVE_MEMBERS", 2):
            result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Unsafe zip archive")
        self.assertEqual(result["details"]["member"], "<archive>")
        self.assertIn("too many entries", result["details"]["reason"])

    def test_restore_extraction_io_failure_returns_structured_error(self):
        backup_name = self._write_backup("restore-extract-fail.zip", _zip_bytes([("world/level.dat", b"level")]))

        with patch("dashboard.services.world_service.shutil.copyfileobj", side_effect=OSError("disk full")):
            result = WorldService.restore_backup(backup_name)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Failed to extract zip archive")
        self.assertEqual(result["details"]["member"], "world/level.dat")
        self.assertIn("disk full", result["details"]["reason"])

    def test_api_world_upload_preserves_structured_error_details(self):
        request = _FakeRequest()
        upload = UploadFile(file=io.BytesIO(b"not-used"), filename="world.zip")

        with patch.object(
            app_module.WorldService,
            "upload_world_zip_bytes",
            return_value={
                "ok": False,
                "error": "Unsafe zip archive",
                "details": {"member": "../outside.txt", "reason": "Path traversal is not allowed"},
            },
        ):
            response = asyncio.run(app_module.api_world_upload(request, upload))

        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.body)
        self.assertEqual(payload["error"], "Unsafe zip archive")
        self.assertEqual(payload["details"]["member"], "../outside.txt")
        self.assertEqual(payload["details"]["reason"], "Path traversal is not allowed")

    def test_api_world_upload_b64_preserves_structured_error_details(self):
        request = _FakeRequest({"archive_b64": "AAA", "filename": "world.zip"})

        with patch.object(
            app_module.WorldService,
            "upload_world_zip_b64",
            return_value={
                "ok": False,
                "error": "Unsafe zip archive",
                "details": {"member": "../outside.txt", "reason": "Path traversal is not allowed"},
            },
        ):
            response = asyncio.run(app_module.api_world_upload_b64(request))

        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.body)
        self.assertEqual(payload["error"], "Unsafe zip archive")
        self.assertEqual(payload["details"]["member"], "../outside.txt")
        self.assertEqual(payload["details"]["reason"], "Path traversal is not allowed")

    def test_api_world_restore_preserves_structured_error_details(self):
        request = _FakeRequest({"name": "backup.zip"})

        with patch.object(
            app_module.WorldService,
            "restore_backup",
            return_value={
                "ok": False,
                "error": "Unsafe zip archive",
                "details": {"member": "../outside.txt", "reason": "Path traversal is not allowed"},
            },
        ):
            response = asyncio.run(app_module.api_world_restore(request))

        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.body)
        self.assertEqual(payload["error"], "Unsafe zip archive")
        self.assertEqual(payload["details"]["member"], "../outside.txt")
        self.assertEqual(payload["details"]["reason"], "Path traversal is not allowed")

    def test_api_world_upload_rejects_oversized_payload_early(self):
        request = _FakeRequest()
        upload = UploadFile(file=io.BytesIO(b"a" * ((2 * 1024 * 1024) + 1)), filename="world.zip")

        with (
            patch.object(app_module.WorldService, "MAX_UPLOAD_BYTES", 2 * 1024 * 1024),
            patch.object(app_module.WorldService, "upload_world_zip_bytes") as upload_world_zip_bytes,
        ):
            response = asyncio.run(app_module.api_world_upload(request, upload))

        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.body)
        self.assertEqual(payload["error"], "Upload too large (max 2 MB)")
        upload_world_zip_bytes.assert_not_called()

    def test_api_world_download_rejects_backslash_name(self):
        request = _FakeRequest()

        with self.assertRaises(HTTPException) as exc:
            asyncio.run(app_module.api_world_download("folder\\backup.zip", request))

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Invalid file")

    def test_api_world_download_rejects_drive_prefixed_name(self):
        request = _FakeRequest()

        with self.assertRaises(HTTPException) as exc:
            asyncio.run(app_module.api_world_download("C:\\backup.zip", request))

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Invalid file")
