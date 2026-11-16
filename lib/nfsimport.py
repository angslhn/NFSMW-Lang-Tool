"""nfsimport -- bangun berkas NFSMW (.bin) dari tabel (.xlsx/.csv).

Tool ini murni alat pindah data: tabel empat kolom (``Index``, ``Key``,
``Label``, ``Text``) ditulis kembali menjadi berkas ``.bin`` yang sah.

Langkahnya:

1. Baca tabel.
2. Cocokkan sidik jari berkas sumber dari lembar ``Meta`` (bila ada).
3. Validasi tiap baris: ``Index``, ``Key``, dan ``Text`` harus sesuai dengan
   berkas sumber, agar perubahan di luar dugaan tidak lolos.
4. Ambil kolom ``Text`` sebagai isi baru.
5. Bangun ulang berkas lewat :func:`nfsbin.rebuild`.
6. Verifikasi: baca ulang hasil, pastikan jumlah entri dan seluruh ``key``
   tidak bergeser serta tiap ``Text`` terbaca persis seperti yang ditulis.

Berkas sumber tidak pernah ditimpa. Hasil selalu ditulis ke berkas baru.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import nfsbin
import nfstable


class ImportRejected(Exception):
    """Impor dihentikan sebelum ada berkas yang ditulis."""


@dataclass
class Issue:
    """Satu temuan selama impor."""

    level: str  # "error" | "warning"
    index: int | None
    label: str
    message: str


@dataclass
class Report:
    """Ringkasan hasil impor."""

    source: Path
    table: Path
    output: Path | None
    total_entries: int = 0
    changed: int = 0
    unchanged: int = 0
    missing_rows: int = 0
    issues: list[Issue] = field(default_factory=list)
    verified: bool = False

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    def describe(self) -> str:
        lines = [
            "Sumber    : %s" % self.source,
            "Tabel     : %s" % self.table,
            "Hasil     : %s" % (self.output if self.output else "(hanya periksa)"),
            "",
            "Entri     : %s" % "{:,}".format(self.total_entries),
            "  berubah : %s" % "{:,}".format(self.changed),
            "  tetap   : %s" % "{:,}".format(self.unchanged),
        ]
        if self.missing_rows:
            lines.append("  baris tabel tidak dipakai: %s" % "{:,}".format(self.missing_rows))

        if self.errors:
            lines += ["", "ERROR (%d):" % len(self.errors)]
            for e in self.errors[:25]:
                lines.append("  [index %s] %s" % (e.index, e.label))
                for part in e.message.splitlines():
                    lines.append("      %s" % part)
            if len(self.errors) > 25:
                lines.append("  ... dan %d error lain" % (len(self.errors) - 25))

        if self.warnings:
            lines += ["", "PERINGATAN (%d):" % len(self.warnings)]
            for w in self.warnings[:15]:
                lines.append("  [index %s] %s: %s" % (w.index, w.label, w.message))
            if len(self.warnings) > 15:
                lines.append("  ... dan %d peringatan lain" % (len(self.warnings) - 15))

        if self.output is not None:
            lines += ["", "Verifikasi: %s" % ("LOLOS" if self.verified else "TIDAK LOLOS")]
        return "\n".join(lines)


def fingerprint(path: str | Path) -> str:
    """SHA-256 berkas."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def check(table_path: str | Path, bin_path: str | Path) -> Report:
    """Validasi tabel tanpa menulis berkas apa pun."""
    return import_table(table_path, bin_path, None, strict=False)


def import_table(
    table_path: str | Path,
    bin_path: str | Path,
    out_path: str | Path | None = None,
    *,
    strict: bool = True,
) -> Report:
    """Bangun berkas ``.bin`` baru dari tabel.

    ``out_path=None`` berarti hanya memeriksa, tidak menulis.
    ``strict=True`` menghentikan impor bila ada error validasi.
    """
    table_path = Path(table_path)
    bin_path = Path(bin_path)

    db = nfsbin.parse(bin_path)
    issues: list[Issue] = []

    header, rows = nfstable.read_rows(table_path)
    _check_header(header, issues)
    _check_meta(nfstable.read_meta(table_path), db, issues)

    by_index: dict[int, dict[str, object]] = {}
    for row in rows:
        try:
            index = int(str(row.get("Index")).strip())
        except (TypeError, ValueError):
            issues.append(Issue("error", None, "-",
                                "Index tidak valid: %r" % row.get("Index")))
            continue
        if index in by_index:
            issues.append(Issue("error", index, str(row.get("Label") or "-"),
                                "Index muncul lebih dari sekali"))
            continue
        by_index[index] = row

    texts = list(db.texts)
    changed = 0
    for index, (key, _) in enumerate(db.entries):
        row = by_index.get(index)
        if row is None:
            continue

        label = str(row.get("Label") or "-")

        excel_key = nfstable.parse_key(row.get("Key"))
        if excel_key is None:
            issues.append(Issue("error", index, label,
                                "Key tidak dapat dibaca: %r" % row.get("Key")))
            continue
        if excel_key != key:
            issues.append(Issue(
                "error", index, label,
                "Key tidak cocok: tabel 0x%08X, berkas 0x%08X" % (excel_key, key)))
            continue

        new_text = row.get("Text")
        new_text = "" if new_text is None else str(new_text)
        try:
            encoded = new_text.encode(nfsbin.ENCODING)
            nfsbin.check_text(encoded, index)
        except (UnicodeEncodeError, ValueError) as exc:
            issues.append(Issue(
                "error", index, label, "Text tidak dapat ditulis: %s" % exc))
            continue

        if encoded != db.texts[index]:
            texts[index] = encoded
            changed += 1

    report = Report(
        source=bin_path,
        table=table_path,
        output=Path(out_path) if out_path else None,
        total_entries=db.count,
        changed=changed,
        unchanged=db.count - changed,
        missing_rows=max(0, db.count - len(by_index)),
        issues=issues,
    )

    if strict and report.errors:
        raise ImportRejected(
            "Impor dibatalkan: %d error validasi." % len(report.errors))

    produced = nfsbin.rebuild(db, texts)

    if out_path is None:
        report.verified = _verify(produced, db, texts, report)
        return report

    report.output = Path(out_path)
    report.output.parent.mkdir(parents=True, exist_ok=True)
    report.output.write_bytes(produced)
    report.verified = _verify(report.output.read_bytes(), db, texts, report)
    return report


# ---------------------------------------------------------------- validasi


def _check_header(header: list[str], issues: list[Issue]) -> None:
    got = [h for h in header if h]
    if got[: len(nfstable.HEADERS)] != nfstable.HEADERS:
        issues.append(Issue(
            "error", None, "-",
            "header tabel tidak cocok.\n    diharapkan: %s\n    terbaca   : %s"
            % (nfstable.HEADERS, got)))


def _check_meta(meta: dict[str, str], db: nfsbin.StringDB, issues: list[Issue]) -> None:
    if not meta:
        issues.append(Issue(
            "warning", None, "-",
            "lembar Meta tidak ada (khas CSV). Pencocokan sumber memakai "
            "Index dan Key saja."))
        return

    recorded = meta.get("SHA-256", "").upper()
    if recorded and recorded != db.sha256:
        issues.append(Issue(
            "error", None, "-",
            "SHA-256 berkas sumber berbeda dari saat ekspor.\n"
            "    saat ekspor : %s\n    sekarang    : %s"
            % (recorded, db.sha256)))

    count = meta.get("Jumlah entri")
    if count and count.isdigit() and int(count) != db.count:
        issues.append(Issue(
            "error", None, "-",
            "jumlah entri berbeda: tabel %s, berkas %d" % (count, db.count)))

    delta = meta.get("delta hdr[1]")
    if delta:
        try:
            if int(delta) != db.hdr1_delta:
                issues.append(Issue(
                    "warning", None, "-",
                    "delta hdr[1] berubah: tabel %s, berkas %d"
                    % (delta, db.hdr1_delta)))
        except ValueError:
            pass


def _verify(raw: bytes, db: nfsbin.StringDB,
            texts: list[bytes], report: Report) -> bool:
    """Urai ulang hasil dan pastikan isinya benar-benar yang dimaksud."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp.write(raw)
        probe = Path(tmp.name)

    try:
        back = nfsbin.parse(probe)
    finally:
        probe.unlink(missing_ok=True)

    for problem in back.problems():
        report.issues.append(Issue("error", None, "-", "hasil: " + problem))

    if back.count != db.count:
        report.issues.append(Issue(
            "error", None, "-",
            "hasil: jumlah entri %d, seharusnya %d" % (back.count, db.count)))
        return False

    if back.keys != db.keys:
        report.issues.append(Issue(
            "error", None, "-", "hasil: daftar key bergeser atau berubah"))
        return False

    mismatch = 0
    for index, expected in enumerate(texts):
        if back.texts[index] != expected:
            mismatch += 1
            if mismatch <= 5:
                report.issues.append(Issue(
                    "error", index, "-",
                    "hasil: teks tidak cocok (ditulis %r, terbaca %r)"
                    % (expected[:40], back.texts[index][:40])))
    if mismatch:
        return False

    return not report.errors


__all__ = ["ImportRejected", "Issue", "Report", "import_table", "check", "fingerprint"]