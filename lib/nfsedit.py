"""nfsedit -- ubah teks dan/atau label satu string yang sudah ada.

``Key`` adalah acuan. Dari satu key, ``Text`` disimpan di berkas bahasa dan
``Label`` disimpan di ``Labels.bin``. Keduanya boleh diubah bersamaan atau
salah satu saja.

Aturan penulisan teks:

- Urutan tabel dan seluruh nilai ``Key`` tidak berubah.
- Hanya teks milik key yang diminta yang berubah. Bila key itu berbagi offset
  dengan key lain, entri tersebut dipindahkan ke offset baru agar pasangannya
  tidak ikut berubah.

Aturan penulisan label:

- Key yang sudah ada di ``Labels.bin`` diperbarui di tempat.
- Key yang belum ada ditambahkan, lalu tabel label diurutkan menurut key.
- Label lain tidak berubah.

Berkas sumber tidak pernah ditimpa. Hasil selalu berkas baru, lalu diurai
ulang untuk memastikan isinya sesuai.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import nfsbin


@dataclass
class EditReport:
    """Ringkasan satu operasi edit string."""

    source: Path
    key: int
    total: int = 0
    old_text: bytes | None = None
    new_text: bytes | None = None
    text_changed: bool = False
    text_output: Path | None = None
    text_offset_shared: bool = False
    label_source: Path | None = None
    old_label: str | None = None
    new_label: str | None = None
    label_changed: bool = False
    label_created: bool = False
    label_output: Path | None = None
    labels_total: int = 0
    verified: bool = False
    problems: list[str] = field(default_factory=list)


def edit_string(
    bin_path: str | Path,
    key: int,
    *,
    text: bytes | None = None,
    label: str | None = None,
    out_path: str | Path | None = None,
    labels_path: str | Path | None = None,
    labels_out: str | Path | None = None,
) -> EditReport:
    """Ubah ``text`` dan/atau ``label`` milik ``key`` di ``bin_path``.

    Minimal salah satu dari ``text`` atau ``label`` harus diisi. ``text``
    berupa bytes Latin-1 tanpa NUL. ``label`` berupa teks biasa yang tidak
    boleh kosong. Label memerlukan ``labels_path``.
    """
    if text is None and label is None:
        raise ValueError("Isi minimal satu: teks atau label.")
    if not isinstance(key, int) or isinstance(key, bool):
        raise ValueError("Key harus berupa angka: %r" % (key,))
    if not 0 < key <= 0xFFFFFFFF:
        raise ValueError("Key 0x%X di luar rentang u32" % key)

    source = Path(bin_path)
    db = nfsbin.parse(source)
    report = EditReport(source=source, key=key, total=db.count)
    present = key in set(db.keys)

    payload: bytes | None = None
    if text is not None:
        if not isinstance(text, (bytes, bytearray)):
            raise ValueError("Teks harus berupa bytes")
        payload = bytes(text)
        if b"\x00" in payload:
            raise ValueError("Teks key 0x%08X mengandung byte NUL" % key)
        try:
            nfsbin.check_text(payload, key)
        except ValueError as exc:
            raise ValueError("Teks tidak dapat ditulis: %s" % exc) from exc
        if not present:
            raise ValueError("Key 0x%08X tidak ada di %s" % (key, source.name))

    label_payload: bytes | None = None
    labels_db: nfsbin.StringDB | None = None
    if label is not None:
        if not isinstance(label, str):
            raise ValueError("Label harus berupa teks")
        if not label:
            raise ValueError("Label tidak boleh kosong")
        try:
            label_payload = label.encode(nfsbin.ENCODING)
        except UnicodeEncodeError as exc:
            raise ValueError(
                "Label tidak dapat diwakili encoding %s: %s"
                % (nfsbin.ENCODING, exc)
            ) from exc
        if b"\x00" in label_payload:
            raise ValueError("Label mengandung byte NUL")
        if labels_path is None:
            raise ValueError("Label memerlukan berkas Labels.bin")
        labels_source = Path(labels_path)
        if labels_source.resolve() == source.resolve():
            raise ValueError(
                "Labels.bin tidak boleh berkas yang sama dengan berkas bahasa"
            )
        labels_db = nfsbin.parse(labels_source)
        report.label_source = labels_source
        report.labels_total = labels_db.count
        labels_map = labels_db.text_by_key()
        if key in labels_map:
            report.old_label = labels_map[key].decode(nfsbin.ENCODING)
        else:
            report.label_created = True

    if not present and labels_db is not None and key not in set(labels_db.keys):
        raise ValueError(
            "Key 0x%08X tidak ada di %s maupun %s"
            % (key, source.name, Path(labels_path).name)
        )

    text_bytes: bytes | None = None
    if payload is not None:
        texts = db.text_by_key()
        report.old_text = texts[key]
        report.new_text = payload
        report.text_changed = report.old_text != payload
        shared = sum(1 for _, off in db.entries
                     if off == _offset_of(db, key)) > 1
        report.text_offset_shared = shared
        text_bytes = nfsbin.replace_text(db, key, payload)
        report.problems.extend(_verify_text(text_bytes, db, key, payload))
        report.text_output = (
            Path(out_path)
            if out_path
            else source.with_name(source.stem + "_edited.bin")
        )
        if report.text_output.resolve() == source.resolve():
            report.problems.append(
                "Hasil tidak boleh menimpa berkas sumber: %s"
                % report.text_output.name
            )

    label_bytes: bytes | None = None
    if labels_db is not None and label_payload is not None:
        report.new_label = label_payload.decode(nfsbin.ENCODING)
        report.label_changed = report.old_label != report.new_label
        if key in set(labels_db.keys):
            label_bytes = nfsbin.replace_text(labels_db, key, label_payload)
        else:
            label_bytes = nfsbin.insert_entries(labels_db, [(key, label_payload)])
        report.problems.extend(
            _verify_labels(
                label_bytes, labels_db, key, label_payload, report.label_created
            )
        )
        report.labels_total = labels_db.count + (1 if report.label_created else 0)
        report.label_output = (
            Path(labels_out)
            if labels_out
            else report.label_source.with_name(
                report.label_source.stem + "_edited.bin"
            )
        )
        clash = {
            report.label_source.resolve(),
            source.resolve(),
        }
        if report.text_output is not None:
            clash.add(report.text_output.resolve())
        if report.label_output.resolve() in clash:
            report.problems.append(
                "Hasil Labels.bin tidak boleh menimpa berkas lain: %s"
                % report.label_output.name
            )
        if (
            report.text_output is not None
            and report.text_output.resolve() == report.label_source.resolve()
        ):
            report.problems.append(
                "Hasil teks tidak boleh menimpa Labels.bin sumber: %s"
                % report.text_output.name
            )

    if report.problems:
        return report

    if text_bytes is not None and report.text_output is not None:
        report.text_output.parent.mkdir(parents=True, exist_ok=True)
        report.text_output.write_bytes(text_bytes)
    if label_bytes is not None and report.label_output is not None:
        report.label_output.parent.mkdir(parents=True, exist_ok=True)
        report.label_output.write_bytes(label_bytes)
    report.verified = True
    return report


def _offset_of(db: nfsbin.StringDB, key: int) -> int:
    for existing, off in db.entries:
        if existing == key:
            return off
    raise ValueError("Key 0x%08X tidak ada di %s" % (key, db.path.name))


def _verify_text(
    raw: bytes,
    db: nfsbin.StringDB,
    key: int,
    payload: bytes,
) -> list[str]:
    problems: list[str] = []
    try:
        back = _parse_bytes(raw)
    except ValueError as exc:
        return ["hasil tidak dapat dibaca: %s" % exc]

    problems += ["hasil: " + item for item in back.problems()]

    if back.count != db.count:
        problems.append(
            "hasil: jumlah entri %d, seharusnya %d" % (back.count, db.count)
        )
    if back.keys != db.keys:
        problems.append("hasil: daftar key berubah")
    if back.keys != sorted(back.keys):
        problems.append("hasil: kolom key tidak terurut naik")

    old = db.text_by_key()
    new = back.text_by_key()
    for other, before in old.items():
        expected = payload if other == key else before
        if new.get(other) != expected:
            problems.append("hasil: teks key 0x%08X tidak sesuai" % other)
            break
    if not problems and nfsbin.rebuild(back) != raw:
        problems.append("hasil: parse -> rebuild tidak identik")
    return problems


def _verify_labels(
    raw: bytes,
    labels_db: nfsbin.StringDB,
    key: int,
    payload: bytes,
    created: bool,
) -> list[str]:
    problems: list[str] = []
    try:
        back = _parse_bytes(raw)
    except ValueError as exc:
        return ["Labels.bin hasil tidak dapat dibaca: %s" % exc]

    problems += ["Labels.bin hasil: " + item for item in back.problems()]

    expected_count = labels_db.count + (1 if created else 0)
    if back.count != expected_count:
        problems.append(
            "Labels.bin hasil: jumlah entri %d, seharusnya %d"
            % (back.count, expected_count)
        )
    if back.keys != sorted(back.keys):
        problems.append("Labels.bin hasil: kolom key tidak terurut naik")
    if len(set(back.keys)) != len(back.keys):
        problems.append("Labels.bin hasil: terdapat key duplikat")

    old = labels_db.text_by_key()
    new = back.text_by_key()
    for other, before in old.items():
        expected = payload if other == key else before
        if new.get(other) != expected:
            problems.append("Labels.bin hasil: label key 0x%08X tidak sesuai" % other)
            break
    if new.get(key) != payload:
        problems.append("Labels.bin hasil: label key 0x%08X tidak terbaca" % key)
    if not problems and nfsbin.rebuild(back) != raw:
        problems.append("Labels.bin hasil: parse -> rebuild tidak identik")
    return problems


def _parse_bytes(raw: bytes) -> nfsbin.StringDB:
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
        tmp.write(raw)
        probe = Path(tmp.name)
    try:
        return nfsbin.parse(probe)
    finally:
        probe.unlink(missing_ok=True)


__all__ = ["EditReport", "edit_string"]
