import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("push_leak_guard", ROOT / "scripts/git-hooks/push_leak_guard.py")
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

ZERO = guard.ZERO_SHA
# Built at runtime so this file holds no literal address for the leak guards.
FAKE_EMAIL = "alguien" + "@" + "dominio-real.com"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class PushLeakGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "dest@example.com")
        git(self.repo, "config", "user.name", "test")
        (self.repo / "a.md").write_text("hola\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "base")
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.cache = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict("os.environ", {"XDG_CACHE_HOME": self.cache.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
        self.cache.cleanup()

    def commit(self, text):
        (self.repo / "b.md").write_text(text)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "cambio")
        return git(self.repo, "rev-parse", "HEAD")

    def run_guard(self, tip, vis, private=()):
        stdin = f"refs/heads/main {tip} refs/heads/main {self.base}\n"
        cwd = Path.cwd()
        with mock.patch.object(guard, "visibility", return_value=vis), \
             mock.patch.object(guard, "private_slugs", return_value=list(private)), \
             mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
             mock.patch.object(sys, "stderr", io.StringIO()):
            try:
                os.chdir(self.repo)
                return guard.main(["pre-push", "origin", "git@github.com:someone/public-repo.git"])
            finally:
                os.chdir(cwd)

    def test_repo_slug(self):
        self.assertEqual(guard.repo_slug("git@github.com:o/r.git"), "o/r")
        self.assertEqual(guard.repo_slug("https://github.com/o/r"), "o/r")
        self.assertIsNone(guard.repo_slug("https://gitlab.com/o/r.git"))

    def test_public_repo_with_email_is_blocked(self):
        tip = self.commit(f"escribe a {FAKE_EMAIL}\n")
        self.assertEqual(self.run_guard(tip, "PUBLIC"), 1)

    def test_private_repo_is_not_scanned(self):
        tip = self.commit(f"escribe a {FAKE_EMAIL}\n")
        self.assertEqual(self.run_guard(tip, "PRIVATE"), 0)

    def test_unknown_visibility_lets_push_through(self):
        tip = self.commit(f"escribe a {FAKE_EMAIL}\n")
        self.assertEqual(self.run_guard(tip, None), 0)

    def test_preserved_placeholder_passes(self):
        tip = self.commit("correo: your.personal.email@gmail.com\n")
        self.assertEqual(self.run_guard(tip, "PUBLIC"), 0)

    def test_private_repo_slug_is_blocked(self):
        tip = self.commit("ver someone/secret-notes y secret-notes#12\n")
        self.assertEqual(self.run_guard(tip, "PUBLIC", ["someone/secret-notes"]), 1)

    def test_branch_deletion_publishes_nothing(self):
        self.assertEqual(guard.push_ranges(f"(delete) {ZERO} refs/heads/x {self.base}\n", "origin"), [])

    def test_update_range_excludes_commits_already_on_remote(self):
        rows = guard.push_ranges(f"refs/heads/x {self.base} refs/heads/x {'1' * 40}\n", "origin")
        self.assertEqual(rows, [[self.base, "--not", "--remotes=origin", "1" * 40]])

    def test_merged_public_commit_is_not_flagged(self):
        # A commit already on a remote-tracking ref (e.g. origin/main) is public:
        # merging it into the pushed branch must not block the push.
        public = self.commit(f"ya publicado {FAKE_EMAIL}\n")
        git(self.repo, "update-ref", "refs/remotes/origin/main", public)
        (self.repo / "c.md").write_text("cambio limpio\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "fix")
        tip = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(self.run_guard(tip, "PUBLIC"), 0)

    def test_new_branch_range_excludes_remote_commits(self):
        rows = guard.push_ranges(f"refs/heads/x {self.base} refs/heads/x {ZERO}\n", "origin")
        self.assertEqual(rows, [[self.base, "--not", "--remotes=origin"]])


if __name__ == "__main__":
    unittest.main()
