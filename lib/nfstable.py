"""nfstable -- definisi kolom dan pembacaan tabel bersama.

Tool ini memindahkan data: basis data string NFSMW (.bin) ke tabel
(Excel/CSV) dan sebaliknya. Tabel memakai empat kolom dengan urutan tetap:

    Index | Key | Label | Text

- ``Index`` : nomor urut entri pada berkas, 0 .. COUNT-1. Kunci baris.
- ``Key``   : nilai u32 dari tabel entri, ditulis heksadesimal. Identitas.
- ``Label`` : nama simbol dari ``Labels.bin``, dicocokkan lewat ``Key``.
- ``Text``  : teks dari berkas bahasa, berkode latin-1.

Tidak ada kolom lain. Isi teks tidak diproses di sini.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import nfsbin

#: Urutan kolom tabel. Jangan diubah tanpa menyesuaikan pembaca impor.
HEADERS = ["Index", "Key", "Label", "Text"]

SHEET_DATA = "Strings"
SHEET_META = "Meta"

COL_INDEX = 0
COL_KEY = 1
COL_LABEL = 2
COL_TEXT = 3

TABULAR_SUFFIX = {".xlsx", ".xlsm", ".csv", ".tsv"}

#: Karakter yang tidak boleh ada di dalam sel ``.xlsx``. Excel menolaknya,
#: jadi saat menulis karakter ini ditulis dengan konvensi OOXML ``_xHHHH_``.
_XML_INVALID = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_OOXML_ESCAPED = re.compile(r"_x([0-9A-Fa-f]{4})_")

#: Kolom yang isinya teks bebas dan perlu melewati escape/unescape OOXML.
TEXT_COLUMNS = (HEADERS[COL_LABEL], HEADERS[COL_TEXT])


def to_sheet_text(text: str) -> str:
    """Ubah teks menjadi bentuk yang aman disimpan di sel ``.xlsx``.

    Excel tidak menerima karakter kontrol (0x00-0x1F) di dalam sel. Format
    OOXML menyimpannya sebagai ``_x0007_`` dan sejenisnya. Agar teks yang
    memang berisi pola ``_xHHHH_`` tidak ikut berubah, garis bawahnya
    dilindungi lebih dulu menjadi ``_x005F_``.

    Tidak ada karakter yang dibuang atau diganti ``?``.
    """
    if not text:
        return text
    text = _OOXML_ESCAPED.sub(lambda m: "_x005F_" + m.group(0)[1:], text)
    return _XML_INVALID.sub(lambda m: "_x%04X_" % ord(m.group(0)), text)


def from_sheet_text(text: str) -> str:
    """Kebalikan :func:`to_sheet_text`. Dipakai saat membaca ``.xlsx``.

    Hanya kode kontrol yang dikembalikan. Pola ``_xHHHH_`` dengan kode
    >= 0x20 dibiarkan apa adanya supaya teks biasa tidak ikut berubah.
    """
    if "_x" not in text:
        return text

    def _decode(match: re.Match) -> str:
        code = int(match.group(1), 16)
        return chr(code) if code < 0x20 else match.group(0)

    return _OOXML_ESCAPED.sub(_decode, text)


@dataclass
class Row:
    """Satu baris tabel: satu entri basis data."""

    index: int
    key: int
    label: str
    text: str

    @property
    def key_hex(self) -> str:
        return "0x%08X" % self.key

    def as_cells(self) -> list[object]:
        return [self.index, self.key_hex, self.label, self.text]


def join_rows(text_db: nfsbin.StringDB, label_db: nfsbin.StringDB | None) -> list[Row]:
    """Gabungkan :file:`English.bin` (teks) dengan :file:`Labels.bin` (label).

    Pencocokan dilakukan pada ``Key``. Bila berkas label tidak diberikan,
    kolom ``Label`` dibiarkan kosong.
    """
    labels: dict[int, str] = {}
    if label_db is not None:
        for key, raw in zip(label_db.keys, label_db.texts):
            labels[key] = raw.decode(nfsbin.ENCODING)

    rows: list[Row] = []
    for index, (key, _) in enumerate(text_db.entries):
        text = text_db.texts[index].decode(nfsbin.ENCODING)
        rows.append(
            Row(index=index, key=key, label=labels.get(key, ""), text=text)
        )
    return rows


def is_tabular(path: str | Path) -> bool:
    return Path(path).suffix.lower() in TABULAR_SUFFIX


# ---------------------------------------------------------------- baca


def read_rows(path: str | Path) -> tuple[list[str], list[dict[str, object]]]:
    """Baca tabel dari ``.xlsx``, ``.csv``, atau ``.tsv``.

    Mengembalikan ``(header, rows)``; tiap baris berupa dict menurut nama kolom.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    if path.suffix.lower() in {".csv", ".tsv"}:
        return _read_delimited(path)
    return _read_xlsx(path)


def _read_delimited(path: Path) -> tuple[list[str], list[dict[str, object]]]:
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    # utf-8-sig menangani BOM yang biasa ditambahkan Excel saat menyimpan CSV.
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            table = list(csv.reader(handle, delimiter=delimiter))
    except UnicodeDecodeError as exc:
        byte = exc.object[exc.start]
        raise ValueError(
            "%s bukan teks UTF-8 (byte 0x%02X di posisi %d tidak dikenal).\n"
            "    Kalau berkas disimpan dari Excel, pilih 'CSV UTF-8 (Comma "
            "delimited)' saat Save As,\n"
            "    bukan 'CSV (Comma delimited)' yang memakai code page lama."
            % (path.name, byte, exc.start)
        ) from exc
    if not table:
        raise ValueError("%s: berkas kosong" % path.name)
    header = [str(c).strip() for c in table[0]]
    rows = [_row_dict(header, raw) for raw in table[1:]
            if raw and any(str(c).strip() for c in raw)]
    return header, rows


def _read_xlsx(path: Path) -> tuple[list[str], list[dict[str, object]]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Membaca .xlsx membutuhkan openpyxl.\n"
            "Pasang dulu: pip install -r requirements.txt"
        ) from exc

    wb = load_workbook(path, data_only=True)
    if SHEET_DATA not in wb.sheetnames:
        raise ValueError(
            "%s: lembar '%s' tidak ada (isinya: %s)"
            % (path.name, SHEET_DATA, ", ".join(wb.sheetnames))
        )
    table = list(wb[SHEET_DATA].iter_rows(values_only=True))
    if not table:
        raise ValueError("%s: lembar '%s' kosong" % (path.name, SHEET_DATA))

    header = ["" if c is None else str(c).strip() for c in table[0]]
    rows: list[dict[str, object]] = []
    for raw in table[1:]:
        if not raw or not any(c is not None and str(c).strip() for c in raw):
            continue
        row = _row_dict(header, raw)
        for name in TEXT_COLUMNS:
            value = row.get(name)
            if isinstance(value, str):
                row[name] = from_sheet_text(value)
        rows.append(row)
    return header, rows


def _row_dict(header: list[str], raw) -> dict[str, object]:
    padded = list(raw) + [None] * max(0, len(header) - len(raw))
    return {name: padded[i] for i, name in enumerate(header) if name}


def read_meta(path: str | Path) -> dict[str, str]:
    """Baca lembar ``Meta`` bila ada. CSV tidak menyimpan meta."""
    path = Path(path)
    if path.suffix.lower() in {".csv", ".tsv"}:
        return {}
    try:
        from openpyxl import load_workbook
    except ImportError:  # pragma: no cover
        return {}
    wb = load_workbook(path, data_only=True)
    if SHEET_META not in wb.sheetnames:
        return {}
    meta: dict[str, str] = {}
    for row in wb[SHEET_META].iter_rows(values_only=True):
        if not row or row[0] is None:
            continue
        key = str(row[0]).strip()
        if key:
            value = row[1] if len(row) > 1 and row[1] is not None else ""
            meta[key] = str(value).strip()
    return meta


def parse_key(value: object) -> int | None:
    """Baca kolom Key: ``0x0000ABCD``, ``43981``, atau angka dari Excel."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text, 10)
    except ValueError:
        return None