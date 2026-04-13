import base64
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path

from ..config import BACKUPS_DIR, MINECRAFT_DIR, PLUGINS_DIR, utc_stamp
from .config_service import PropertiesService
from .server_service import ServerService


class SeedService:
    @staticmethod
    def random_seed() -> str:
        import random
        return str(random.randint(-(2**63) + 1, (2**63) - 1))

    @staticmethod
    def get_seed() -> str:
        return PropertiesService.read_all().get('level-seed', '')

    @staticmethod
    def apply_seed(seed: str) -> dict:
        s = str(seed).strip()
        if len(s) > 64:
            return {'ok': False, 'error': 'Seed too long (max 64)'}
        props = PropertiesService.read_all()
        props['level-seed'] = s
        PropertiesService.write_all(props)
        return {'ok': True, 'message': 'Seed updated.', 'seed': s}


class WorldService:
    MAX_UPLOAD_BYTES = 200 * 1024 * 1024
    MAX_ARCHIVE_MEMBERS = 100_000
    MAX_ARCHIVE_UNCOMPRESSED_BYTES = 8 * 1024 * 1024 * 1024

    @staticmethod
    def _unsafe_archive_error(member: str, reason: str) -> dict:
        return {
            'ok': False,
            'error': 'Unsafe zip archive',
            'details': {'member': member, 'reason': reason},
        }

    @staticmethod
    def _extract_archive_error(member: str, reason: str) -> dict:
        return {
            'ok': False,
            'error': 'Failed to extract zip archive',
            'details': {'member': member, 'reason': reason},
        }

    @staticmethod
    def _corrupt_archive_error(member: str) -> dict:
        return {
            'ok': False,
            'error': f'Corrupt zip member: {member}',
            'details': {'member': member, 'reason': 'Member failed integrity check'},
        }

    @staticmethod
    def _invalid_archive_error(reason: str = 'Archive is not a readable zip file') -> dict:
        return {
            'ok': False,
            'error': 'Invalid zip archive',
            'details': {'reason': reason},
        }

    @staticmethod
    def _zip_member_target(member_name: str, destination: Path) -> tuple[Path | None, dict | None]:
        if not member_name:
            return None, WorldService._unsafe_archive_error(member_name, 'Empty member name')
        if '\x00' in member_name:
            return None, WorldService._unsafe_archive_error(member_name, 'NUL byte in member name')

        normalized = member_name.replace('\\', '/')
        if normalized.startswith('/'):
            return None, WorldService._unsafe_archive_error(member_name, 'Absolute paths are not allowed')
        if re.match(r'^[a-zA-Z]:', normalized):
            return None, WorldService._unsafe_archive_error(member_name, 'Drive-prefixed paths are not allowed')

        parts = [p for p in normalized.split('/') if p and p != '.']
        if any(p == '..' for p in parts):
            return None, WorldService._unsafe_archive_error(member_name, 'Path traversal is not allowed')

        if not parts:
            # Directory marker like "/" or "./" has no extractable target.
            return None, None

        dest_root = destination.resolve()
        target = (dest_root / Path(*parts)).resolve()
        try:
            target.relative_to(dest_root)
        except ValueError:
            return None, WorldService._unsafe_archive_error(member_name, 'Entry resolves outside extraction directory')
        return target, None

    @staticmethod
    def _validate_zip_members(zf: zipfile.ZipFile, destination: Path) -> dict | None:
        infos = zf.infolist()
        if len(infos) > WorldService.MAX_ARCHIVE_MEMBERS:
            return WorldService._unsafe_archive_error(
                '<archive>',
                f'Archive has too many entries ({len(infos)} > {WorldService.MAX_ARCHIVE_MEMBERS})',
            )

        total_uncompressed = 0
        max_uncompressed = WorldService.MAX_ARCHIVE_UNCOMPRESSED_BYTES

        for info in infos:
            file_size = max(0, int(getattr(info, 'file_size', 0) or 0))
            total_uncompressed += file_size
            if total_uncompressed > max_uncompressed:
                return WorldService._unsafe_archive_error(
                    info.filename,
                    (
                        'Archive uncompressed size exceeds limit '
                        f'({total_uncompressed} > {max_uncompressed} bytes)'
                    ),
                )

            mode = (info.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(mode):
                return WorldService._unsafe_archive_error(info.filename, 'Symlink entries are not allowed')

            _target, err = WorldService._zip_member_target(info.filename, destination)
            if err:
                return err
        return None

    @staticmethod
    def _safe_extract_zip(zf: zipfile.ZipFile, destination: Path) -> dict | None:
        validation_error = WorldService._validate_zip_members(zf, destination)
        if validation_error:
            return validation_error

        for info in zf.infolist():
            target, err = WorldService._zip_member_target(info.filename, destination)
            if err:
                return err
            if target is None:
                continue

            if info.is_dir() or info.filename.endswith('/'):
                try:
                    target.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    return WorldService._extract_archive_error(info.filename, str(exc) or 'Directory create failure')
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, 'r') as src, open(target, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            except Exception as exc:
                return WorldService._extract_archive_error(info.filename, str(exc) or 'I/O extraction failure')
        return None

    @staticmethod
    def _resolve_backup_path(backup_name: str) -> Path | None:
        if not isinstance(backup_name, str):
            return None

        normalized = backup_name.strip().replace('\\', '/')
        if not normalized or '\x00' in normalized:
            return None
        if normalized.startswith('/') or normalized.startswith('//'):
            return None
        if re.match(r'^[a-zA-Z]:', normalized):
            return None
        if '/' in normalized or '..' in normalized:
            return None

        backup_root = BACKUPS_DIR.resolve()
        backup_path = (backup_root / normalized).resolve()
        try:
            backup_path.relative_to(backup_root)
        except ValueError:
            return None
        return backup_path

    @staticmethod
    def level_name() -> str:
        return PropertiesService.read_all().get('level-name', 'world') or 'world'

    @staticmethod
    def world_path() -> Path:
        return MINECRAFT_DIR / WorldService.level_name()

    @staticmethod
    def dimensions_paths(base_world: Path) -> list[Path]:
        return [base_world, MINECRAFT_DIR / f'{base_world.name}_nether', MINECRAFT_DIR / f'{base_world.name}_the_end']

    @staticmethod
    def ensure_backup_dir() -> None:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def create_backup() -> dict:
        world = WorldService.world_path()
        if not world.exists():
            return {'ok': False, 'error': f'World not found: {world}'}

        WorldService.ensure_backup_dir()
        out_path = BACKUPS_DIR / f'{world.name}-{utc_stamp()}.zip'

        with zipfile.ZipFile(out_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for base in WorldService.dimensions_paths(world):
                if not base.exists():
                    continue
                for root, _dirs, files in os.walk(base):
                    for fn in files:
                        fp = Path(root) / fn
                        arc = fp.relative_to(MINECRAFT_DIR)
                        zf.write(fp, arcname=str(arc))

        return {'ok': True, 'path': str(out_path), 'name': out_path.name}

    @staticmethod
    def list_backups(limit: int = 30) -> list[dict]:
        if not BACKUPS_DIR.exists():
            return []
        files = sorted(BACKUPS_DIR.glob('*.zip'), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return [{'name': p.name, 'size_mb': round(p.stat().st_size / (1024 * 1024), 2), 'updated_at': int(p.stat().st_mtime)} for p in files]

    @staticmethod
    def delete_world_files() -> None:
        world = WorldService.world_path()
        for p in WorldService.dimensions_paths(world):
            if p.exists():
                shutil.rmtree(p)

    @staticmethod
    def reset_world(with_backup: bool = True, new_seed: str | None = None) -> dict:
        was_running = ServerService.is_running()
        if was_running:
            ServerService.stop()

        backup_info = WorldService.create_backup() if with_backup else None
        if with_backup and (not backup_info or not backup_info.get('ok')):
            if was_running:
                ServerService.start()
            return {
                'ok': False,
                'error': (backup_info or {}).get('error', 'Backup failed before reset'),
                'backup': backup_info,
            }

        if new_seed is not None:
            seed_result = SeedService.apply_seed(new_seed)
            if not seed_result.get('ok'):
                if was_running:
                    ServerService.start()
                return {'ok': False, 'error': seed_result.get('error', 'Failed to update seed'), 'backup': backup_info}

        WorldService.delete_world_files()

        if was_running:
            ServerService.start()

        return {'ok': True, 'backup': backup_info, 'message': 'World reset complete'}

    @staticmethod
    def restore_backup(backup_name: str) -> dict:
        backup_path = WorldService._resolve_backup_path(backup_name)
        if backup_path is None:
            return {'ok': False, 'error': 'Invalid backup name'}
        if not backup_path.exists() or not backup_path.is_file():
            return {'ok': False, 'error': 'Backup not found'}

        try:
            with zipfile.ZipFile(backup_path, 'r') as zf:
                unsafe = WorldService._validate_zip_members(zf, MINECRAFT_DIR)
                if unsafe:
                    return unsafe
                test = zf.testzip()
                if test:
                    return WorldService._corrupt_archive_error(test)
        except zipfile.BadZipFile:
            return WorldService._invalid_archive_error('Bad zip file')
        except Exception as exc:
            return WorldService._invalid_archive_error(str(exc) or 'Archive open/read failure')

        was_running = ServerService.is_running()
        if was_running:
            ServerService.stop()

        try:
            WorldService.delete_world_files()
            with zipfile.ZipFile(backup_path, 'r') as zf:
                unsafe = WorldService._safe_extract_zip(zf, MINECRAFT_DIR)
                if unsafe:
                    return unsafe
        except zipfile.BadZipFile:
            return WorldService._invalid_archive_error('Bad zip file')
        except Exception as exc:
            return WorldService._extract_archive_error('<archive>', str(exc) or 'Archive extraction failure')
        finally:
            if was_running:
                ServerService.start()
        return {'ok': True, 'message': f'Restored backup {backup_name}'}

    @staticmethod
    def upload_world_zip_b64(archive_b64: str, filename: str = 'uploaded-world.zip') -> dict:
        try:
            raw = base64.b64decode(archive_b64)
        except Exception:
            return {'ok': False, 'error': 'Invalid base64 payload'}
        return WorldService.upload_world_zip_bytes(raw, filename)

    @staticmethod
    def upload_world_zip_bytes(raw: bytes, filename: str = 'uploaded-world.zip') -> dict:
        if len(raw) > WorldService.MAX_UPLOAD_BYTES:
            return {'ok': False, 'error': 'Upload too large'}

        WorldService.ensure_backup_dir()
        safe_name = ''.join(c for c in filename if c.isalnum() or c in ('-', '_', '.')) or 'uploaded-world.zip'
        tmp_zip = BACKUPS_DIR / f'upload-{utc_stamp()}-{safe_name}'
        tmp_zip.write_bytes(raw)

        def _cleanup_tmp_zip() -> None:
            try:
                tmp_zip.unlink(missing_ok=True)
            except Exception:
                pass

        validation_result = None
        try:
            with zipfile.ZipFile(tmp_zip, 'r') as zf:
                unsafe = WorldService._validate_zip_members(zf, MINECRAFT_DIR)
                if unsafe:
                    validation_result = unsafe
                else:
                    test = zf.testzip()
                    if test:
                        validation_result = WorldService._corrupt_archive_error(test)
        except zipfile.BadZipFile:
            _cleanup_tmp_zip()
            return WorldService._invalid_archive_error('Bad zip file')
        except Exception as exc:
            _cleanup_tmp_zip()
            return WorldService._invalid_archive_error(str(exc) or 'Archive open/read failure')

        if validation_result:
            _cleanup_tmp_zip()
            return validation_result

        was_running = ServerService.is_running()
        if was_running:
            ServerService.stop()

        try:
            WorldService.delete_world_files()
            with zipfile.ZipFile(tmp_zip, 'r') as zf:
                unsafe = WorldService._safe_extract_zip(zf, MINECRAFT_DIR)
                if unsafe:
                    _cleanup_tmp_zip()
                    return unsafe
        except zipfile.BadZipFile:
            _cleanup_tmp_zip()
            return WorldService._invalid_archive_error('Bad zip file')
        except Exception as exc:
            _cleanup_tmp_zip()
            return WorldService._extract_archive_error('<archive>', str(exc) or 'Archive extraction failure')
        finally:
            if was_running:
                ServerService.start()

        return {'ok': True, 'message': 'World uploaded and applied', 'stored_as': tmp_zip.name}
