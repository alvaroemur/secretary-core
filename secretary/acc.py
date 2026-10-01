"""Action ledger operations: fold a closure, archive closed entries, look up by id."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from secretary.config import resolve_path_key


def fold_action(
    acc_id: str,
    evidencia: str,
    cerrado: str | None = None,
    estado: str | None = None,
    module: str = "meetings",
) -> str:
    cerrado = cerrado or date.today().isoformat()
    estado = estado or os.environ.get("SEC_ACC_ESTADO", "hecha")

    path = _ledger_path(module)
    if not path.is_file():
        raise FileNotFoundError(f"No existe {path}")

    text = path.read_text(encoding="utf-8")
    header = f"## {acc_id}\n"
    idx = text.find(header)
    if idx == -1:
        if _find_in_archive(path.parent, acc_id):
            raise ValueError(f"{acc_id} ya está archivada (acciones/archivo/)")
        raise LookupError(f"No encontré entrada canónica {acc_id}")

    if "[update]" in text[idx : idx + len(header) + 10]:
        raise ValueError(f"{acc_id} no es entrada canónica")

    next_hdr = text.find("\n## ", idx + len(header))
    block = text[idx : next_hdr if next_hdr != -1 else len(text)]

    def set_field(b: str, key: str, value: str) -> str:
        pat = re.compile(rf"^- {re.escape(key)}:.*$", re.M)
        repl = f"- {key}: {value}"
        if pat.search(b):
            return pat.sub(repl, b, count=1)
        return b.rstrip() + f"\n{repl}\n"

    block = set_field(block, "estado", estado)
    block = set_field(block, "cerrado", cerrado)
    block = set_field(block, "evidencia_cierre", evidencia)

    new_text = text[:idx] + block + text[next_hdr if next_hdr != -1 else len(text) :]

    fold = f"""
---

## {acc_id} [update]
- estado_nuevo: {estado}
- evidencia: Fold canónico vía secretary acc fold ({evidencia}).
- evidencia_cierre: {evidencia}
- cerrado: {cerrado}
- origen: interactive:secretary-acc-fold
- detectado: {cerrado}
"""

    path.write_text(new_text.rstrip() + fold, encoding="utf-8")
    return f"✓ {acc_id} → {estado} · {evidencia} · cerrado {cerrado}"


# --- Ledger parsing -------------------------------------------------------------------

CLOSED_STATES = frozenset({"hecha", "cancelada", "caducada"})
DEFAULT_RETENTION_DAYS = 14

# Any `## acc-<8 digits>…` line starts a block. The template headers in the file preamble
# (`acc-YYYYMMDD-NNN`) have no digits there, so they stay in the preamble. Headers that are
# not exactly `acc-YYYYMMDD-NNN` [+ ` [update]`] (ranges like `acc-… al 005`, suffixed ids)
# become their own `irregular` blocks so they never travel with a neighbour.
_HEADER_RE = re.compile(r"^## (acc-\d{8}[^\n]*?)[ \t]*$", re.M)
_REGULAR_HEADER_RE = re.compile(r"(acc-\d{8}-\d+)([ \t]+\[update\])?")
_FIELD_RE = re.compile(r"^- ([^\W\d]\w*):[ \t]*(.*)$", re.M)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _ledger_path(module: str) -> Path:
    return resolve_path_key(f"{module}.memory") / "acciones.md"


def _archive_dir(ledger: Path) -> Path:
    return ledger.parent / "acciones" / "archivo"


@dataclass(frozen=True)
class Block:
    """One `## acc-…` block, kept verbatim so a split/join is lossless."""

    raw: str
    acc_id: str
    is_update: bool
    fields: dict[str, str]
    irregular: bool = False

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.raw.strip().encode("utf-8")).hexdigest()

    @property
    def estado(self) -> str:
        value = self.fields.get("estado") or self.fields.get("estado_nuevo") or ""
        return value.split()[0] if value else ""

    @property
    def cerrado(self) -> date | None:
        m = _DATE_RE.match(self.fields.get("cerrado", ""))
        try:
            return date.fromisoformat(m.group(0)) if m else None
        except ValueError:
            return None

    @property
    def pendiente_wiki(self) -> bool:
        return self.fields.get("pendiente_wiki", "").lower().startswith("true")


def parse_ledger(text: str) -> tuple[str, list[Block]]:
    """Split into (preamble, blocks). `preamble + "".join(b.raw for b in blocks) == text`."""
    heads = list(_HEADER_RE.finditer(text))
    if not heads:
        return text, []
    blocks: list[Block] = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        raw = text[m.start() : end]
        fields: dict[str, str] = {}
        for fm in _FIELD_RE.finditer(raw):
            fields.setdefault(fm.group(1), fm.group(2).strip())
        reg = _REGULAR_HEADER_RE.fullmatch(m.group(1))
        if reg:
            blocks.append(Block(raw, reg.group(1), bool(reg.group(2)), fields))
        else:
            blocks.append(Block(raw, m.group(1), False, fields, irregular=True))
    return text[: heads[0].start()], blocks


def _find_in_archive(memory_dir: Path, acc_id: str) -> list[tuple[Path, Block]]:
    found: list[tuple[Path, Block]] = []
    arch = memory_dir / "acciones" / "archivo"
    if not arch.is_dir():
        return found
    for f in sorted(arch.glob("*.md")):
        _, blocks = parse_ledger(f.read_text(encoding="utf-8"))
        found.extend((f, b) for b in blocks if b.acc_id == acc_id)
    return found


def show_action(acc_id: str, module: str = "meetings") -> list[tuple[str, Block]]:
    """Locate an acc-id: active ledger first, then the monthly archive. Returns (location, block)."""
    ledger = _ledger_path(module)
    hits: list[tuple[str, Block]] = []
    if ledger.is_file():
        _, blocks = parse_ledger(ledger.read_text(encoding="utf-8"))
        hits.extend((ledger.name, b) for b in blocks if b.acc_id == acc_id)
    hits.extend((f"acciones/archivo/{f.name}", b) for f, b in _find_in_archive(ledger.parent, acc_id))
    if not hits:
        raise LookupError(f"No encontré {acc_id} en el activo ni en el archivo")
    return hits


# --- Archive --------------------------------------------------------------------------


@dataclass
class ArchivePlan:
    moves: dict[str, list[Block]] = field(default_factory=dict)  # "YYYY-MM" -> blocks
    kept: int = 0
    skipped: dict[str, list[str]] = field(default_factory=dict)  # reason -> acc-ids

    @property
    def moved_count(self) -> int:
        return sum(len(v) for v in self.moves.values())


def plan_archive(
    blocks: list[Block],
    today: date | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> ArchivePlan:
    """Decide which closed entries (plus their `[update]` blocks) move to the monthly archive.

    An id is moved only when it is unambiguous and safe: one canonical block, state closed,
    a valid `cerrado` older than the retention window, and no block of that id still
    waiting for `wiki-update` (`pendiente_wiki: true`). Everything else stays and is reported.
    """
    today = today or date.today()
    cutoff = today - timedelta(days=retention_days)
    plan = ArchivePlan()

    def skip(reason: str, acc_id: str) -> None:
        plan.skipped.setdefault(reason, []).append(acc_id)

    for b in blocks:
        if b.irregular:
            skip("encabezado-irregular", b.acc_id)
    regular = [b for b in blocks if not b.irregular]
    canon_count = Counter(b.acc_id for b in regular if not b.is_update)
    by_id: dict[str, list[Block]] = {}
    for b in regular:
        by_id.setdefault(b.acc_id, []).append(b)

    move_ids: dict[str, str] = {}  # acc_id -> month
    for acc_id, group in by_id.items():
        canon = [b for b in group if not b.is_update]
        if not canon:
            skip("update-huerfano", acc_id)
            continue
        if canon_count[acc_id] > 1:
            skip("id-duplicado", acc_id)
            continue
        c = canon[0]
        if not c.estado:
            skip("sin-estado", acc_id)
            continue
        if c.estado not in CLOSED_STATES:
            continue  # alive: stays, not worth reporting
        if any(b.pendiente_wiki for b in group):
            skip("pendiente-wiki", acc_id)
            continue
        closed = c.cerrado
        if closed is None:
            skip("sin-cerrado", acc_id)
            continue
        if closed > cutoff:
            continue  # inside the retention window: stays
        move_ids[acc_id] = closed.strftime("%Y-%m")

    for b in regular:
        month = move_ids.get(b.acc_id)
        if month:
            plan.moves.setdefault(month, []).append(b)
    plan.kept = len(blocks) - plan.moved_count
    return plan


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _join_blocks(blocks: list[Block]) -> str:
    return "".join(b.raw if b.raw.endswith("\n") else b.raw + "\n" for b in blocks)


def archive_actions(
    module: str = "meetings",
    apply: bool = False,
    today: date | None = None,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> tuple[ArchivePlan, dict[str, int]]:
    """Plan (default) or apply the archive. Returns (plan, stats).

    Apply order keeps data safe on a crash: archive files first (verified by re-reading),
    active ledger last. A re-run after a crash is a no-op for blocks already archived.
    Raises ValueError if any invariant check fails; nothing is replaced in that case.
    """
    ledger = _ledger_path(module)
    if not ledger.is_file():
        raise FileNotFoundError(f"No existe {ledger}")
    text = ledger.read_text(encoding="utf-8")
    preamble, blocks = parse_ledger(text)
    if preamble + "".join(b.raw for b in blocks) != text:
        raise ValueError("parse_ledger no es lossless; abortando")

    plan = plan_archive(blocks, today=today, retention_days=retention_days)
    moved_ids = {b.acc_id for group in plan.moves.values() for b in group}
    kept_blocks = [b for b in blocks if b.irregular or b.acc_id not in moved_ids]
    new_active = preamble + "".join(b.raw for b in kept_blocks)
    stats = {
        "bytes_before": len(text.encode("utf-8")),
        "bytes_after": len(new_active.encode("utf-8")),
        "blocks_before": len(blocks),
        "blocks_after": len(kept_blocks),
    }
    if not apply or not plan.moves:
        return plan, stats

    arch = _archive_dir(ledger)
    new_archives: dict[Path, str] = {}
    for month, group in plan.moves.items():
        target = arch / f"{month}.md"
        if target.is_file():
            existing = target.read_text(encoding="utf-8")
            _, ex_blocks = parse_ledger(existing)
            ex_canon = {b.acc_id: b.digest for b in ex_blocks if not b.is_update}
            for b in group:
                if not b.is_update and ex_canon.get(b.acc_id, b.digest) != b.digest:
                    raise ValueError(f"{b.acc_id} ya existe en {target.name} con contenido distinto")
            have = {b.digest for b in ex_blocks}
            fresh = [b for b in group if b.digest not in have]
            body = existing if existing.endswith("\n") else existing + "\n"
            new_archives[target] = body + _join_blocks(fresh)
        else:
            new_archives[target] = f"# Acciones — archivo {month}\n\n" + _join_blocks(group)

    # Invariant: original multiset == kept + moved (by content hash).
    before = Counter(b.digest for b in blocks)
    after = Counter(b.digest for b in kept_blocks) + Counter(b.digest for g in plan.moves.values() for b in g)
    if before != after:
        raise ValueError("verificación fallida: el conjunto de bloques cambiaría")

    for target, content in new_archives.items():
        _atomic_write(target, content)
        _, written = parse_ledger(target.read_text(encoding="utf-8"))
        have = {b.digest for b in written}
        missing = [b.acc_id for b in plan.moves[target.stem] if b.digest not in have]
        if missing:
            raise ValueError(f"verificación fallida en {target.name}: faltan {missing[:5]}")
    _atomic_write(ledger, new_active)
    return plan, stats
