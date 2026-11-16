"""nfstxt -- jembatan tabel (.xlsx/.csv) dengan berkas teks sederhana.

Format txt sengaja dibuat sesederhana mungkin supaya mudah dibaca dan
diedit::

    0, @
    1, GPS
    2, LAP

Tiap baris berisi ``Index``, koma, satu spasi, lalu ``Text`` apa adanya.
Teks boleh mengandung koma; yang dipakai sebagai pemisah hanya koma
pertama. Teks yang diawali spasi tetap utuh karena hanya satu spasi setelah
koma yang dibuang.

Karakter kontrol tidak ditulis mentah karena akan merusak pembacaan baris
(``U+0085`` dan ``U+000B`` misalnya dianggap akhir baris oleh banyak alat).
Karakter itu ditulis sebagai escape::

    133, Defeat Ho Seun \\x82Sonny\\x83

Escape yang dipakai: ``\\\\`` (garis miring), ``\\n``, ``\\r``, ``\\t``, dan
``\\xHH`` untuk byte kontrol 0x00-0x1F serta 0x7F-0x9F. Teks lain ditulis
apa adanya, termasuk huruf beraksen.

Alur pakai:

1. :func:`write_txt`  -- ambil kolom ``Index`` dan ``Text`` dari tabel.
2. Teks diedit di berkas ``.txt``.
3. :func:`build_from_txt` -- tulis kembali tabel empat kolom dengan
   ``Index``, ``Key``, dan ``Label`` dari tabel dasar, ``Text`` dari txt.

Dengan begitu cukup dua kolom yang disentuh, sementara tabel yang dihasilkan
tetap lengkap dan siap diimpor menjadi ``.bin``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import nfsbin
import nfstable

__all__ = [
    "TxtResult",
    "BuildResult",
    "write_txt",
    "read_txt",
    "build_from_txt",
    "default_txt_path",
]

#: Satu spasi setelah koma adalah pemisah, bukan bagian dari teks.
SEPARATOR = ", "


@dataclass
class TxtResult:
    """Ringkasan hasil konversi tabel -> txt."""

    source: Path
    output: Path
    rows: int


@dataclass
class BuildResult:
    """Ringkasan hasil konversi txt -> tabel."""

    txt: Path
    base: Path
    output: Path
    rows: int
    applied: int
    missing: list[int] = field(default_factory=list)
    unchanged: int = 0


def default_txt_path(table_path: str | Path) -> Path:
    """``English.xlsx`` -> ``English.txt``."""
    return Path(table_path).with_suffix(".txt")


def escape_text(text: str) -> str:
    """Ubah karakter kontrol menjadi escape yang aman dibaca per baris."""
    out: list[str] = []
    for char in text:
        code = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif code < 0x20 or 0x7F <= code <= 0x9F:
            out.append("\\x%02X" % code)
        else:
            out.append(char)
    return "".join(out)


def unescape_text(text: str, where: str = "teks") -> str:
    """Kebalikan :func:`escape_text`. Escape tak dikenal ditolak."""
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue
        if i + 1 >= len(text):
            raise ValueError("%s: garis miring di akhir tanpa kode escape" % where)
        nxt = text[i + 1]
        if nxt == "\\":
            out.append("\\")
            i += 2
        elif nxt == "n":
            out.append("\n")
            i += 2
        elif nxt == "r":
            out.append("\r")
            i += 2
        elif nxt == "t":
            out.append("\t")
            i += 2
        elif nxt == "x":
            code = text[i + 2:i + 4]
            if len(code) != 2 or any(c not in "0123456789abcdefABCDEF" for c in code):
                raise ValueError(
                    "%s: '\\x' harus diikuti dua digit hex, mis. \\x85" % where
                )
            out.append(chr(int(code, 16)))
            i += 4
        else:
            raise ValueError(
                "%s: escape '\\%s' tidak dikenal (garis miring ditulis \\\\)"
                % (where, nxt)
            )
    return "".join(out)


def write_txt(table_path: str | Path, out_path: str | Path | None = None) -> TxtResult:
    """Tulis kolom ``Index`` dan ``Text`` dari tabel menjadi berkas txt."""
    table = Path(table_path)
    _, rows = nfstable.read_rows(table)

    out = Path(out_path) if out_path else default_txt_path(table)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen: set[int] = set()
    written: dict[int, str] = {}
    lines: list[str] = []
    for row in rows:
        index = _row_index(row)
        if index in seen:
            raise ValueError("%s: Index %d muncul lebih dari sekali" % (table.name, index))
        seen.add(index)

        text = "" if row.get("Text") is None else str(row.get("Text"))
        written[index] = text
        lines.append("%d%s%s" % (index, SEPARATOR, escape_text(text)))

    with out.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\n".join(lines))
        if lines:
            handle.write("\n")

    # Pastikan txt yang baru ditulis terbaca kembali persis seperti tabel.
    if read_txt(out) != written:
        raise RuntimeError(
            "%s: isi txt tidak terbaca sama setelah ditulis" % out.name
        )

    return TxtResult(source=table, output=out, rows=len(lines))


def read_txt(path: str | Path) -> dict[int, str]:
    """Baca txt menjadi ``{index: text}``.

    Baris kosong dan baris komentar (diawali ``#``) dilewati. Header
    ``Index, Text`` boleh ada. Koma pertama adalah pemisah; sisa baris
    dianggap teks, jadi koma di dalam teks aman.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            content = handle.read()
    except UnicodeDecodeError as exc:
        byte = exc.object[exc.start]
        raise ValueError(
            "%s bukan teks UTF-8 (byte 0x%02X di posisi %d tidak dikenal)."
            % (path.name, byte, exc.start)
        ) from exc

    data: dict[int, str] = {}
    for number, raw in enumerate(content.split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        head, sep, rest = line.partition(",")
        if not sep:
            raise ValueError(
                "%s baris %d: tidak ada koma. Formatnya 'index, text'."
                % (path.name, number)
            )

        key = head.strip()
        if not key.lstrip("-").isdigit():
            if key.lower() == "index":
                # Header opsional, boleh didahului baris komentar.
                continue
            raise ValueError(
                "%s baris %d: '%s' bukan Index angka." % (path.name, number, key)
            )

        index = int(key)
        if index < 0:
            raise ValueError("%s baris %d: Index negatif." % (path.name, number))
        if index in data:
            raise ValueError(
                "%s baris %d: Index %d muncul lebih dari sekali."
                % (path.name, number, index)
            )
        if rest.startswith(" "):
            rest = rest[1:]
        data[index] = unescape_text(
            rest, "%s baris %d" % (path.name, number)
        )

    if not data:
        raise ValueError("%s: tidak ada baris 'index, text'." % path.name)
    return data


def build_from_txt(
    txt_path: str | Path,
    base_table: str | Path,
    out_path: str | Path | None = None,
) -> BuildResult:
    """Tulis tabel baru memakai teks dari txt dan kerangka dari tabel dasar."""
    txt = Path(txt_path)
    base = Path(base_table)

    suffix = base.suffix.lower()
    if suffix not in nfstable.TABULAR_SUFFIX:
        raise ValueError(
            "%s bukan tabel .xlsx/.csv yang bisa dipakai sebagai dasar" % base.name
        )

    wanted = read_txt(txt)
    _, rows = nfstable.read_rows(base)

    base_indices = [_row_index(row) for row in rows]
    known = set(base_indices)

    extra = sorted(set(wanted) - known)
    if extra:
        shown = ", ".join(str(i) for i in extra[:10])
        if len(extra) > 10:
            shown += ", ..."
        raise ValueError(
            "Index berikut tidak ada di tabel dasar %s: %s"
            % (base.name, shown)
        )

    bad: list[str] = []
    for index, text in wanted.items():
        try:
            payload = text.encode(nfsbin.ENCODING)
            nfsbin.check_text(payload, index)
        except (UnicodeEncodeError, ValueError) as exc:
            bad.append("index %d: %s" % (index, exc))
            if len(bad) >= 5:
                break
    if bad:
        raise ValueError(
            "Teks tidak dapat ditulis ke .bin:\n    " + "\n    ".join(bad)
        )

    expected: list[tuple[int, int, str, str]] = []
    for row in rows:
        index = _row_index(row)
        text = wanted.get(index, "" if row.get("Text") is None else str(row.get("Text")))
        expected.append((
            index,
            nfstable.parse_key(row.get("Key")) or 0,
            "" if row.get("Label") is None else str(row.get("Label")),
            text,
        ))

    suffix = base.suffix.lower()
    out = Path(out_path) if out_path else base.with_name(txt.stem + "_new" + base.suffix)
    if out.resolve() == base.resolve() or out.resolve() == txt.resolve():
        raise ValueError("Hasil tidak boleh menimpa berkas sumber: %s" % out.name)
    out.parent.mkdir(parents=True, exist_ok=True)

    if suffix in {".csv", ".tsv"}:
        _write_csv_updated(base, out, expected)
    else:
        _write_xlsx_updated(base, out, wanted)

    _verify(out, expected)

    missing = sorted(known - set(wanted))
    return BuildResult(
        txt=txt,
        base=base,
        output=out,
        rows=len(expected),
        applied=len(wanted),
        missing=missing,
        unchanged=len(expected) - len(wanted),
    )


# ---------------------------------------------------------------- tulis


def _write_xlsx_updated(base: Path, out: Path, wanted: dict[int, str]) -> None:
    """Perbarui kolom Text di salinan tabel .xlsx, lembar Meta ikut terjaga."""
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Menulis .xlsx membutuhkan openpyxl.\n"
            "Pasang dulu: pip install -r requirements.txt"
        ) from exc

    workbook = load_workbook(base, keep_vba=base.suffix.lower() == ".xlsm")
    if nfstable.SHEET_DATA not in workbook.sheetnames:
        raise ValueError(
            "%s: lembar '%s' tidak ada (isinya: %s)"
            % (base.name, nfstable.SHEET_DATA, ", ".join(workbook.sheetnames))
        )

    sheet = workbook[nfstable.SHEET_DATA]
    columns = _columns(sheet, base.name)

    found: set[int] = set()
    for row_number in range(2, sheet.max_row + 1):
        value = sheet.cell(row=row_number, column=columns["Index"]).value
        if value is None or str(value).strip() == "":
            continue
        index = _as_index(value, base.name)
        if index in wanted:
            sheet.cell(row=row_number, column=columns["Text"]).value = (
                nfstable.to_sheet_text(wanted[index])
            )
            found.add(index)

    if found != set(wanted):
        missing = sorted(set(wanted) - found)
        shown = ", ".join(str(i) for i in missing[:10])
        if len(missing) > 10:
            shown += ", ..."
        raise ValueError(
            "%s: Index berikut tidak ditemukan di lembar %s: %s"
            % (base.name, nfstable.SHEET_DATA, shown)
        )
    workbook.save(out)


def _write_csv_updated(
    base: Path,
    out: Path,
    expected: list[tuple[int, int, str, str]],
) -> None:
    delimiter = "\t" if base.suffix.lower() == ".tsv" else ","
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=delimiter)
        writer.writerow(nfstable.HEADERS)
        for index, key, label, text in expected:
            writer.writerow([index, "0x%08X" % key, label, text])


def _columns(sheet, name: str) -> dict[str, int]:
    """Petakan nama kolom ke nomor kolom berdasarkan baris pertama."""
    found: dict[str, int] = {}
    for cell in next(sheet.iter_rows(min_row=1, max_row=1)):
        if cell.value is None:
            continue
        found[str(cell.value).strip()] = cell.column
    needed = {"Index": nfstable.HEADERS[0], "Text": nfstable.HEADERS[3]}
    missing = [label for label, key in needed.items() if key not in found]
    if missing:
        raise ValueError(
            "%s: kolom %s tidak ditemukan di baris pertama lembar %s"
            % (name, ", ".join(missing), nfstable.SHEET_DATA)
        )
    return {label: found[key] for label, key in needed.items()}


# ---------------------------------------------------------------- bantu


def _row_index(row: dict[str, object]) -> int:
    value = row.get("Index")
    if value is None:
        raise ValueError("ada baris tanpa Index")
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValueError("Index tidak valid: %r" % value) from exc


def _as_index(value: object, name: str) -> int:
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValueError("%s: Index tidak valid: %r" % (name, value)) from exc


def _verify(out: Path, expected: list[tuple[int, int, str, str]]) -> None:
    """Baca ulang hasil dan bandingkan seluruh empat kolom."""
    _, rows = nfstable.read_rows(out)
    if len(rows) != len(expected):
        raise RuntimeError(
            "hasil %s berisi %d baris, seharusnya %d"
            % (out.name, len(rows), len(expected))
        )
    for row, (index, key, label, text) in zip(rows, expected):
        if _row_index(row) != index:
            raise RuntimeError("hasil %s: Index tidak cocok" % out.name)
        if (nfstable.parse_key(row.get("Key")) or 0) != key:
            raise RuntimeError(
                "hasil %s: Key index %d berubah (0x%08X)"
                % (out.name, index, (nfstable.parse_key(row.get("Key")) or 0))
            )
        got_label = "" if row.get("Label") is None else str(row.get("Label"))
        got_text = "" if row.get("Text") is None else str(row.get("Text"))
        if got_label != label or got_text != text:
            raise RuntimeError(
                "hasil %s: isi index %d tidak cocok setelah ditulis" % (out.name, index)
            )
