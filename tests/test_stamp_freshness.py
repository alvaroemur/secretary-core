import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "secretary/routines/ops/stamp-freshness.py"
spec = importlib.util.spec_from_file_location("stamp_freshness", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

AT = "2026-11-23T22:05:00-05:00"


@pytest.mark.parametrize("old", ['"2026-11-01T18:20:00-05:00"', "2026-10-09", "null"])
def test_stamps_quoted_unquoted_and_null(old):
    text = f"kind: extractor\nfreshness:\n  sla: daily\n  last_success_at: {old}\nsink:\n  memory: x\n"
    out = mod.stamp(text, AT)
    assert f'  last_success_at: "{AT}"\n' in out
    assert out.replace(f'"{AT}"', old) == text


def test_keeps_trailing_comment():
    out = mod.stamp('freshness:\n  last_success_at: null  # pending\n', AT)
    assert out == f'freshness:\n  last_success_at: "{AT}"  # pending\n'


def test_missing_key_fails(tmp_path):
    p = tmp_path / "contract.yaml"
    p.write_text("freshness:\n  sla: daily\n", encoding="utf-8")
    assert mod.main([str(p), "--at", AT]) == 1


def test_cli_writes_file(tmp_path):
    p = tmp_path / "contract.yaml"
    p.write_text("freshness:\n  last_success_at: 2026-10-09\n", encoding="utf-8")
    assert mod.main([str(p), "--at", AT]) == 0
    assert p.read_text(encoding="utf-8") == f'freshness:\n  last_success_at: "{AT}"\n'
