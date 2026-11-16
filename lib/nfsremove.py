"""nfsremove -- hapus string dari basis data bahasa NFSMW.

Satu atau beberapa ``key`` dihapus dari berkas bahasa. Tabel menyusut 8 byte
per entri, awal blob dan seluruh offset digeser, lalu header dihitung ulang.
Seluruh key dan teks yang tersisa harus tetap sama persis.

``Label`` tidak disimpan di berkas bahasa. Bila diminta, key yang sama juga
dihapus dari salinan ``Labels.bin`` supaya labelnya tidak menggantung.

Berkas sumber tidak pernah ditimpa. Hasil selalu berkas baru.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import nfsbin


@dataclass
class RemoveReport:
    """Ringkasan satu operasi hapus string."""

    source: Path
    output: Path | None
    total_before: int = 0
    total_after: int = 0
    removed: list[tuple[int, bytes]] = field(default_factory=list)
    verified: bool = False
    problems: list[str] = field(default_factory=list)
    label_source: Path | None = None
    label_output: Path | None = None
    labels_removed: list[tuple[int, str]] = field(default_factory=list)
    labels_missing: list[int] = field(default_factory=list)
    labels_total: int = 0

    @property
    def removed_count(self) -> int:
        return len(self.removed)


def remove_strings(
    bin_path: str | Path,
    keys: list[int],
    out_path: str | Path | None = None,
    *,
    labels_path: str | Path | None = None,
    labels_out: str | Path | None = None,
) -> RemoveReport:
    """Hapus ``keys`` dari ``bin_path`` dan tulis hasilnya ke berkas baru.

    ``labels_path`` opsional: bila diberikan, key yang sama ikut dihapus dari
    salinan ``Labels.bin``. Key yang tidak punya label di berkas itu dicatat
    sebagai :attr:`RemoveReport.labels_missing`.
    """
    source = Path(bin_path)
    db = nfsbin.parse(source)
    total_before = db.count

    clean = _validate(db, keys)
    texts = db.text_by_key()
    removed = [(key, texts[key]) for key in clean]

    out = Path(out_path) if out_path else source.with_name(source.stem + "_new.bin")
    if out.resolve() == source.resolve():
        raise ValueError("Hasil tidak boleh menimpa berkas sumber: %s" % out.name)

    produced = nfsbin.remove_entries(db, clean)
    problems = _verify(produced, db, clean)

    report = RemoveReport(
        source=source,
        output=out,
        total_before=total_before,
        total_after=total_before - len(clean),
        removed=removed,
        verified=not problems,
        problems=problems,
    )
    if problems:
        return report

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(produced)

    if labels_path:
        _remove_labels(report, Path(labels_path), labels_out, out)
    report.verified = report.verified and not report.problems
    return report


def _validate(db: nfsbin.StringDB, keys: list[int]) -> list[int]:
    if not keys:
        raise ValueError("Tidak ada string yang akan dihapus.")

    clean: list[int] = []
    seen: set[int] = set()
    for key in keys:
        if not isinstance(key, int) or isinstance(key, bool):
            raise ValueError("Key harus berupa angka: %r" % (key,))
        if not 0 < key <= 0xFFFFFFFF:
            raise ValueError("Key 0x%X di luar rentang u32" % key)
        if key in seen:
            raise ValueError("Key 0x%08X muncul lebih dari sekali" % key)
        seen.add(key)
        clean.append(key)

    existing = set(db.keys)
    missing = [key for key in clean if key not in existing]
    if missing:
        raise ValueError(
            "Key %s tidak ada di %s"
            % (", ".join("0x%08X" % key for key in missing[:5]), db.path.name)
        )
    return clean


def _verify(
    raw: bytes,
    db: nfsbin.StringDB,
    removed: list[int],
) -> list[str]:
    problems: list[str] = []
    try:
        back = _parse_bytes(raw)
    except ValueError as exc:
        return ["hasil tidak dapat dibaca: %s" % exc]

    problems += ["hasil: " + item for item in back.problems()]

    drop = set(removed)
    expected_count = db.count - len(removed)
    if back.count != expected_count:
        problems.append(
            "hasil: jumlah entri %d, seharusnya %d"
            % (back.count, expected_count)
        )

    expected_keys = [key for key in db.keys if key not in drop]
    if back.keys != expected_keys:
        problems.append("hasil: daftar key tidak sama dengan yang dimaksud")
    if set(back.keys) & drop:
        problems.append("hasil: key yang dihapus masih ada")
    if back.keys != sorted(back.keys):
        problems.append("hasil: kolom key tidak terurut naik")

    old = db.text_by_key()
    new = back.text_by_key()
    for key in expected_keys:
        if new.get(key) != old[key]:
            problems.append("hasil: teks key 0x%08X berubah" % key)
            break

    if not problems and nfsbin.rebuild(back) != raw:
        problems.append("hasil: parse -> rebuild tidak identik")

    return problems


def _remove_labels(
    report: RemoveReport,
    labels_path: Path,
    labels_out: str | Path | None,
    language_out: Path,
) -> None:
    labels_db = nfsbin.parse(labels_path)
    report.label_source = labels_path
    report.labels_total = labels_db.count

    if labels_path.resolve() == report.source.resolve():
        report.problems.append(
            "Labels.bin tidak boleh berkas yang sama dengan berkas bahasa"
        )
        return

    labels = labels_db.text_by_key()
    present = [key for key, _ in report.removed if key in labels]
    report.labels_missing = [
        key for key, _ in report.removed if key not in labels
    ]
    if not present:
        return

    out = (
        Path(labels_out)
        if labels_out
        else labels_path.with_name(labels_path.stem + "_new.bin")
    )
    if out.resolve() in {
        labels_path.resolve(),
        report.source.resolve(),
        language_out.resolve(),
    }:
        report.problems.append(
            "Hasil Labels.bin tidak boleh menimpa berkas sumber: %s" % out.name
        )
        return

    produced = nfsbin.remove_entries(labels_db, present)
    problems = _verify(produced, labels_db, present)
    if problems:
        report.problems.extend("Labels.bin: " + item for item in problems)
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(produced)
    report.label_output = out
    report.labels_removed = [
        (key, labels[key].decode(nfsbin.ENCODING)) for key in present
    ]
    report.labels_total = labels_db.count - len(present)


def _parse_bytes(raw: bytes) -> nfsbin.StringDB:
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp.write(raw)
        probe = Path(tmp.name)
    try:
        return nfsbin.parse(probe)
    finally:
        probe.unlink(missing_ok=True)


__all__ = ["RemoveReport", "remove_strings"]
