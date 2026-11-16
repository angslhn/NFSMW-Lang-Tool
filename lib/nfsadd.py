"""nfsadd -- tambah string baru ke basis data bahasa NFSMW.

Satu entri baru terdiri dari ``key``, ``label``, dan ``text``. Yang
benar-benar disimpan di berkas bahasa hanyalah ``key`` dan ``text``;
``label`` adalah nama bantu untuk kolom ``Label``. Karena itu label dapat
ikut ditulis ke salinan ``Labels.bin`` supaya muncul lagi saat Export
berikutnya.

Langkah penulisan:

1. Entri baru ditambahkan ke daftar.
2. Seluruh daftar diurutkan menurut ``key`` (game melakukan pencarian biner).
3. Jumlah entri, alamat entri terakhir, penunjuk akhir blob, dan offset tiap
   entri dihitung ulang.
4. Berkas hasil dibaca ulang dan dibandingkan dengan sumber: seluruh key dan
   teks lama harus tetap sama, entri baru harus terbaca persis.

Berkas sumber tidak pernah ditimpa. Hasil selalu berkas baru.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import nfsbin


@dataclass
class AddReport:
    """Ringkasan satu operasi tambah string."""

    source: Path
    output: Path | None
    total_before: int = 0
    total_after: int = 0
    additions: list[tuple[int, str, bytes]] = field(default_factory=list)
    verified: bool = False
    problems: list[str] = field(default_factory=list)
    label_source: Path | None = None
    label_output: Path | None = None
    labels_added: int = 0
    labels_skipped: list[tuple[int, str]] = field(default_factory=list)
    labels_total: int = 0

    @property
    def added(self) -> int:
        return len(self.additions)


def decode_escapes(text: str) -> str:
    """Ubah ``\\xHH`` menjadi karakternya; escape lain dibiarkan apa adanya.

    Hanya pola ``\\x`` + dua digit hex yang ditafsirkan, sehingga teks biasa
    seperti ``C:\\Games`` tidak berubah.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if (
            text[i] == "\\"
            and i + 3 < len(text)
            and text[i + 1] in "xX"
            and all(c in "0123456789abcdefABCDEF" for c in text[i + 2:i + 4])
        ):
            out.append(chr(int(text[i + 2:i + 4], 16)))
            i += 4
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def add_strings(
    bin_path: str | Path,
    additions: list[tuple[int, str, bytes]],
    out_path: str | Path | None = None,
    *,
    labels_path: str | Path | None = None,
    labels_out: str | Path | None = None,
) -> AddReport:
    """Tambah entri ke ``bin_path`` dan tulis hasilnya ke berkas baru.

    ``additions`` berisi ``(key, label, teks)``. ``teks`` sudah berupa bytes
    latin-1. ``labels_path`` opsional: bila diberikan, label untuk key yang
    belum ada di berkas itu ikut ditambahkan ke salinan ``Labels.bin``.
    """
    source = Path(bin_path)
    db = nfsbin.parse(source)
    total_before = db.count

    clean = _validate(db, additions)

    out = Path(out_path) if out_path else source.with_name(source.stem + "_new.bin")
    if out.resolve() == source.resolve():
        raise ValueError("Hasil tidak boleh menimpa berkas sumber: %s" % out.name)

    payloads = [(key, text) for key, _, text in clean]
    produced = nfsbin.insert_entries(db, payloads)
    problems = _verify(produced, db, clean)

    report = AddReport(
        source=source,
        output=out,
        total_before=total_before,
        total_after=total_before + len(clean),
        additions=clean,
        verified=not problems,
        problems=problems,
    )
    if problems:
        return report

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(produced)

    if labels_path:
        _add_labels(report, Path(labels_path), labels_out, out)
    report.verified = report.verified and not report.problems
    return report


def _validate(
    db: nfsbin.StringDB, additions: list[tuple[int, str, bytes]]
) -> list[tuple[int, str, bytes]]:
    if not additions:
        raise ValueError("Tidak ada string baru untuk ditambahkan.")

    keys = db.keys
    if keys != sorted(keys):
        raise ValueError("%s: kolom key tidak terurut naik" % db.path.name)
    if len(set(keys)) != len(keys):
        raise ValueError("%s: terdapat key duplikat" % db.path.name)

    seen = set(keys)
    clean: list[tuple[int, str, bytes]] = []
    for key, label, text in additions:
        if not isinstance(key, int) or isinstance(key, bool):
            raise ValueError("Key harus berupa angka: %r" % (key,))
        if not 0 < key <= 0xFFFFFFFF:
            raise ValueError("Key 0x%X di luar rentang u32" % key)
        if key in seen:
            raise ValueError("Key 0x%08X sudah ada di %s" % (key, db.path.name))
        seen.add(key)

        label = "" if label is None else str(label)
        try:
            encoded_label = label.encode(nfsbin.ENCODING)
        except UnicodeEncodeError as exc:
            raise ValueError(
                "Label tidak dapat diwakili encoding %s: %s"
                % (nfsbin.ENCODING, exc)
            ) from exc
        if b"\x00" in encoded_label:
            raise ValueError("Label mengandung byte NUL")

        if not isinstance(text, (bytes, bytearray)):
            raise ValueError("Teks key 0x%08X harus berupa bytes" % key)
        text = bytes(text)
        if b"\x00" in text:
            raise ValueError("Teks key 0x%08X mengandung byte NUL" % key)
        try:
            nfsbin.check_text(text)
        except ValueError as exc:
            raise ValueError(
                "Teks key 0x%08X tidak dapat ditulis: %s" % (key, exc)
            ) from exc

        clean.append((key, label, text))
    return clean


def _verify(
    raw: bytes,
    db: nfsbin.StringDB,
    additions: list[tuple[int, str, bytes]],
) -> list[str]:
    problems: list[str] = []
    try:
        back = _parse_bytes(raw)
    except ValueError as exc:
        return ["hasil tidak dapat dibaca: %s" % exc]

    problems += ["hasil: " + item for item in back.problems()]

    expected_count = db.count + len(additions)
    if back.count != expected_count:
        problems.append(
            "hasil: jumlah entri %d, seharusnya %d"
            % (back.count, expected_count)
        )

    expected_keys = set(db.keys)
    expected_keys.update(key for key, _, _ in additions)
    if set(back.keys) != expected_keys:
        problems.append("hasil: daftar key tidak sama dengan yang dimaksud")
    if back.keys != sorted(back.keys):
        problems.append("hasil: kolom key tidak terurut naik")

    old = db.text_by_key()
    new = back.text_by_key()
    for key, text in old.items():
        if new.get(key) != text:
            problems.append(
                "hasil: teks lama key 0x%08X berubah" % key
            )
            break
    for key, _, text in additions:
        if new.get(key) != text:
            problems.append(
                "hasil: teks baru key 0x%08X tidak terbaca persis" % key
            )

    if not problems and nfsbin.rebuild(back) != raw:
        problems.append("hasil: parse -> rebuild tidak identik")

    return problems


def _add_labels(
    report: AddReport,
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

    existing = set(labels_db.keys)
    new_labels: list[tuple[int, bytes]] = []
    for key, label, _ in report.additions:
        if not label:
            continue
        if key in existing:
            report.labels_skipped.append((key, label))
            continue
        try:
            payload = label.encode(nfsbin.ENCODING)
            nfsbin.check_text(payload)
        except (UnicodeEncodeError, ValueError) as exc:
            report.problems.append(
                "label key 0x%08X tidak dapat ditulis ke Labels.bin: %s"
                % (key, exc)
            )
            continue
        new_labels.append((key, payload))

    if not new_labels:
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

    produced = nfsbin.insert_entries(labels_db, new_labels)
    problems = _verify(produced, labels_db, [
        (key, "", payload) for key, payload in new_labels
    ])
    if problems:
        report.problems.extend("Labels.bin: " + item for item in problems)
        return

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(produced)
    report.label_output = out
    report.labels_added = len(new_labels)
    report.labels_total = labels_db.count + len(new_labels)


def _parse_bytes(raw: bytes) -> nfsbin.StringDB:
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp.write(raw)
        probe = Path(tmp.name)
    try:
        return nfsbin.parse(probe)
    finally:
        probe.unlink(missing_ok=True)


__all__ = ["AddReport", "add_strings", "decode_escapes"]
