import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dashboard.services.log_analytics_service import LogService


class _BrokenLogPath:
    def exists(self):
        return True

    def open(self, *args, **kwargs):
        raise OSError("boom")

    def __str__(self):
        return "/definitely/not/real.log"


class LogServiceTailTests(unittest.TestCase):
    def test_tail_missing_log_returns_no_logs_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "latest.log"
            with patch("dashboard.services.log_analytics_service.LOG_FILE", missing):
                self.assertEqual(LogService.tail(), "No logs yet.")

    def test_tail_returns_last_n_lines_without_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "latest.log"
            log_file.write_text("line1\nline2\nline3\n", encoding="utf-8")

            with patch("dashboard.services.log_analytics_service.LOG_FILE", log_file):
                self.assertEqual(LogService.tail(lines=2), "line2\nline3")

    def test_tail_read_failure_returns_clear_error(self):
        broken = _BrokenLogPath()
        with patch("dashboard.services.log_analytics_service.LOG_FILE", broken):
            self.assertEqual(LogService.tail(lines=5), "Failed to read logs")


if __name__ == "__main__":
    unittest.main()
