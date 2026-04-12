import importlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import dashboard.app as app_module
import dashboard.config as config_module
from dashboard.services.plugin_service import PluginService


class _FakeDownloadResponse:
    def __init__(self, data: bytes, final_url: str):
        self._buf = io.BytesIO(data)
        self._final_url = final_url

    def read(self, n: int = -1) -> bytes:
        return self._buf.read(n)

    def geturl(self) -> str:
        return self._final_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class AuthProxyTrustTests(unittest.TestCase):
    def test_client_key_ignores_forwarded_for_by_default(self):
        from dashboard.auth import client_key

        class _Client:
            host = '10.0.0.5'

        class _Req:
            headers = {'x-forwarded-for': '203.0.113.99'}
            client = _Client()

        with patch('dashboard.auth.TRUST_X_FORWARDED_FOR', False):
            key = client_key(_Req(), 'Admin')
        self.assertEqual(key, '10.0.0.5:admin')

    def test_client_key_honors_forwarded_for_when_enabled(self):
        from dashboard.auth import client_key

        class _Client:
            host = '10.0.0.5'

        class _Req:
            headers = {'x-forwarded-for': '203.0.113.99'}
            client = _Client()

        with patch('dashboard.auth.TRUST_X_FORWARDED_FOR', True):
            key = client_key(_Req(), 'Admin')
        self.assertEqual(key, '203.0.113.99:admin')


class SecurityHardeningTests(unittest.TestCase):
    def test_mutating_api_requires_csrf_token(self):
        client = TestClient(app_module.app)

        with (
            patch("dashboard.app.check_login", return_value=True),
            patch.object(app_module.ServerService, "start", return_value="started"),
            patch.object(app_module.WorldService, "create_backup", return_value={"ok": True, "name": "backup.zip"}),
        ):
            login = client.post("/api/login", json={"username": "admin", "password": "x"})
            self.assertEqual(login.status_code, 200)

            no_csrf = client.post("/api/start")
            self.assertEqual(no_csrf.status_code, 403)

            csrf = client.get("/api/csrf")
            self.assertEqual(csrf.status_code, 200)
            token = csrf.json().get("csrf_token", "")
            self.assertTrue(token)

            with_csrf = client.post("/api/start", headers={"X-CSRF-Token": token})
            self.assertEqual(with_csrf.status_code, 200)

            # world download-url is mutating and must require CSRF + POST
            wrong_method = client.get("/api/world/download-url")
            self.assertEqual(wrong_method.status_code, 405)

            missing_csrf = client.post("/api/world/download-url")
            self.assertEqual(missing_csrf.status_code, 403)

            with_csrf_download = client.post("/api/world/download-url", headers={"X-CSRF-Token": token})
            self.assertEqual(with_csrf_download.status_code, 200)

    def test_plugin_stage_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            fake_dir = config_module.Path(td)
            fake_data = b"not-the-expected-jar" * 128
            fake_url = "https://cdn.modrinth.com/data/example/plugin.jar"

            catalog = [
                {
                    "id": "demo-plugin",
                    "name": "Demo Plugin",
                    "url": fake_url,
                    "kind": "plugin",
                    "sha256": "0" * 64,
                    "allowed_hosts": ["cdn.modrinth.com"],
                }
            ]

            with (
                patch.object(PluginService, "CATALOG", catalog),
                patch("dashboard.services.plugin_service.PLUGINS_DIR", fake_dir),
                patch("dashboard.services.plugin_service.load_plugins_index", return_value=[]),
                patch("dashboard.services.plugin_service.save_plugins_index"),
                patch(
                    "dashboard.services.plugin_service.urllib.request.urlopen",
                    return_value=_FakeDownloadResponse(fake_data, fake_url),
                ),
            ):
                result = PluginService.stage_from_catalog("demo-plugin")

            self.assertFalse(result.get("ok"), result)
            self.assertIn("hash", result.get("error", "").lower())

    def test_default_bind_host_is_loopback(self):
        env = dict(os.environ)
        env.pop("BIND_HOST", None)

        with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, env, clear=True):
            reloaded = importlib.reload(config_module)
            self.assertEqual(reloaded.BIND_HOST, "127.0.0.1")

        # Restore expected process-global config module state after the isolated reload.
        importlib.reload(config_module)

    def test_login_rejects_invalid_json_with_400(self):
        client = TestClient(app_module.app)
        response = client.post("/api/login", content='{"username":', headers={"Content-Type": "application/json"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid JSON payload"})

    def test_login_rejects_non_object_json_with_400(self):
        client = TestClient(app_module.app)
        response = client.post("/api/login", json=["not-an-object"])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "JSON body must be an object"})

    def test_plugin_remove_rejects_empty_and_windows_style_paths(self):
        self.assertFalse(PluginService.remove_staged("").get("ok"))
        self.assertFalse(PluginService.remove_staged("..\\evil.jar").get("ok"))
        self.assertFalse(PluginService.remove_staged("C:plugin.jar").get("ok"))

    def test_server_service_run_uses_shell_false_with_argv(self):
        from dashboard.services import server_service as ss

        with patch("dashboard.services.server_service.subprocess.run") as mock_run:
            ss.run(["tmux", "has-session", "-t", "demo"])

        mock_run.assert_called_once_with(["tmux", "has-session", "-t", "demo"], text=True, capture_output=True)

    def test_arx_cli_dashboard_checks_use_bind_host(self):
        from scripts import arx_cli as cli

        with patch.object(cli, 'bind_host', return_value='0.0.0.0'), \
             patch.object(cli, 'bind_port', return_value=18890), \
             patch.object(cli, '_find_dashboard_procs', return_value=[]), \
             patch.object(cli, '_port_open', return_value=True) as mock_port_open:
            ok, _msg = cli._start_dashboard()

        self.assertTrue(ok)
        mock_port_open.assert_called_once_with('0.0.0.0', 18890)


if __name__ == "__main__":
    unittest.main()
