"""--close del latido: publica desde un worktree efímero aunque main esté sucio."""
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "secretary/routines/ops/sec-heartbeat-state.sh"
LATEST = """# Heartbeat
- timestamp: 2026-10-31 07:20 (America/Lima)
- slot: on-demand

## Lectura
- listo
"""


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def setup(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    inst = tmp_path / "inst"
    git(tmp_path, "clone", "-q", str(origin), str(inst))
    git(inst, "config", "user.email", "t@t")
    git(inst, "config", "user.name", "t")
    (inst / "ajeno.txt").write_text("a\n")
    (inst / "subsystem/heartbeat").mkdir(parents=True)
    (inst / "subsystem/heartbeat/latest.md").write_text("viejo\n")
    git(inst, "add", ".")
    git(inst, "commit", "-q", "-m", "base")
    git(inst, "push", "-q", "origin", "main")
    return origin, inst


def run_close(inst, tmp_path):
    env = {
        **os.environ,
        "SECRETARY_INSTANCE": str(inst),
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "HEARTBEAT_STATUS_CMD": str(tmp_path / "bin/secretary"),
    }
    return subprocess.run(["bash", str(SCRIPT), "--close"], env=env, capture_output=True, text=True)


def test_close_con_main_sucio_publica_y_no_toca_cambios_ajenos(tmp_path):
    origin, inst = setup(tmp_path)
    (inst / "ajeno.txt").write_text("trabajo de otra sesión\n")
    (inst / "subsystem/heartbeat/latest.md").write_text(LATEST)
    r = run_close(inst, tmp_path)
    assert r.returncode == 0, r.stderr
    assert (inst / "ajeno.txt").read_text() == "trabajo de otra sesión\n"
    pub = git(origin, "show", "main:subsystem/heartbeat/latest.md")
    assert "listo" in pub
    assert "## Latido 07:20 (on-demand)" in git(origin, "show", "main:subsystem/heartbeat/2026-10-31.md")
    assert git(origin, "log", "-1", "--format=%s", "main").startswith("chore(heartbeat): latido on-demand")
    assert not (tmp_path / "state/secretary/heartbeat-fallos").exists()


def test_close_fallido_cuenta_y_alerta_al_segundo(tmp_path):
    _, inst = setup(tmp_path)
    (inst / "subsystem/heartbeat/latest.md").write_text("# Heartbeat\n<!-- lectura: pendiente -->\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    called = tmp_path / "called"
    stub = bin_dir / "secretary"
    stub.write_text(f'#!/bin/sh\necho "$@" >> {called}\n')
    stub.chmod(0o755)
    assert run_close(inst, tmp_path).returncode != 0
    assert not called.exists()
    assert run_close(inst, tmp_path).returncode != 0
    assert "falló 2 corridas seguidas" in called.read_text()
