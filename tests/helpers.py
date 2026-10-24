"""Shared test setup: a throwaway copy of the fictional sample user."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sherpa import cli, db  # noqa: E402


class AlexHome(unittest.TestCase):
    """Each test gets its own copy of examples/alex as SHERPA_HOME."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / "alex"
        shutil.copytree(REPO / "examples" / "alex", self.home)
        self._old = os.environ.get("SHERPA_HOME")
        os.environ["SHERPA_HOME"] = str(self.home)

    def tearDown(self):
        db.close_all()
        if self._old is None:
            os.environ.pop("SHERPA_HOME", None)
        else:
            os.environ["SHERPA_HOME"] = self._old
        self._tmp.cleanup()

    def run_cli(self, *argv, stdin: str | None = None) -> str:
        """Run a sherpa command; returns its output. SystemExit propagates."""
        out = io.StringIO()
        old_stdin = sys.stdin
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            with contextlib.redirect_stdout(out):
                cli.main(list(argv))
        finally:
            sys.stdin = old_stdin
        return out.getvalue()
