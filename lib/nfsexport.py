"""nfsexport -- ekspor basis data string NFSMW (.bin) ke tabel (.xlsx/.csv).

Tool ini murni alat pindah data. Ia membaca berkas bahasa NFSMW dan
menuliskan seluruh entrinya ke tabel empat kolom:

    Index | Key | Label | Text

``Label`` diisi dari ``Labels.bin`` bila berkas itu diberikan. Pencocokan
antara berkas bahasa dan berkas label dilakukan pada ``Key``, bukan pada
posisi, karena jumlah entri keduanya berbeda.

Nama berkas hasil mengikuti nama berkas sumber: ``English.bin`` menjadi
``English.xlsx``.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import nfsbin
import nfstable


@dataclass
class ExportResult:
    """Ringkasan hasil ekspor."""

    source: Path
    output: Path
    label_source: Path | None
    rows: int
    labeled: int

    def describe(self) -> str:
        return "\n".join([
            "Sumber   : %s" % self.source,
            "Label    : %s" % (self.label_source or "(tidak dipakai)"),
            "Hasil    : %s" % self.output,
            "",
            "Baris    : %s" % "{:,}".format(self.rows),
            "Berlabel : %s" % "{:,}".format(self.labeled),
            "Tanpa    : %s" % "{:,}".format(self.rows - self.labeled),
        ])


def default_output(bin_path: str | Path, fmt: str) -> Path:
    """``English.bin`` -> ``English.xlsx`` atau ``English.csv``."""
    p = Path(bin_path)
    suffix = ".csv" if fmt.lower() == "csv" else ".xlsx"
    return p.with_name(p.stem + suffix)


def resolve_output(out_path: str | Path | None, source: Path, fmt: str) -> Path:
    """Tentukan berkas tujuan.

    ``None``      -> nama baku dari berkas sumber.
    berakhiran    -> dipakai apa adanya.
    selain itu    -> dianggap folder, diisi nama baku.
    """
    suffix = ".csv" if fmt.lower() == "csv" else ".xlsx"
    if out_path is None:
        return default_output(source, fmt)
    p = Path(out_path)
    if p.suffix.lower() in nfstable.TABULAR_SUFFIX:
        return p
    return p / default_output(source, suffix).name


def export(
    bin_path: str | Path,
    out_path: str | Path | None = None,
    label_path: str | Path | None = None,
    fmt: str = "xlsx",
) -> ExportResult:
    """Ekspor satu berkas bahasa (+ opsional berkas label) ke tabel."""
    text_db = nfsbin.parse(bin_path)
    label_db = nfsbin.parse(label_path) if label_path else None
    rows = nfstable.join_rows(text_db, label_db)

    out = resolve_output(out_path, text_db.path, fmt)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.suffix.lower() == ".csv":
        _write_csv(out, rows)
    else:
        _write_xlsx(out, rows, text_db, label_db)

    return ExportResult(
        source=text_db.path,
        output=out,
        label_source=label_db.path if label_db else None,
        rows=len(rows),
        labeled=sum(1 for r in rows if r.label),
    )


# ---------------------------------------------------------------- CSV


def _write_csv(out: Path, rows: list[nfstable.Row]) -> None:
    with out.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(nfstable.HEADERS)
        for row in rows:
            writer.writerow(row.as_cells())


# ---------------------------------------------------------------- XLSX


COL_WIDTH = {1: 8, 2: 13, 3: 36, 4: 70}


def _write_xlsx(out: Path, rows: list[nfstable.Row], text_db, label_db) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()

    ws = wb.active
    ws.title = nfstable.SHEET_DATA
    ws.append(nfstable.HEADERS)

    head_fill = PatternFill("solid", fgColor="1F3D5C")
    head_font = Font(bold=True, color="FFFFFF")
    for col in range(1, len(nfstable.HEADERS) + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill = head_fill
        cell.font = head_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = COL_WIDTH[col]

    wrap = Alignment(vertical="top", wrap_text=True)
    for row in rows:
        ws.append([
            row.index,
            row.key_hex,
            nfstable.to_sheet_text(row.label),
            nfstable.to_sheet_text(row.text),
        ])
        for col in (nfstable.COL_LABEL + 1, nfstable.COL_TEXT + 1):
            ws.cell(row=ws.max_row, column=col).alignment = wrap

    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = "A1:%s%d" % (
            get_column_letter(len(nfstable.HEADERS)), len(rows) + 1)

    _write_meta(wb.create_sheet(nfstable.SHEET_META), text_db, label_db, len(rows))
    wb.save(out)


def _write_meta(ws, text_db, label_db, row_count: int) -> None:
    from openpyxl.styles import Font

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 78

    def add(label: str, value: object) -> None:
        ws.append([label, value])
        if label:
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True)

    add("Dibuat", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    add("", "")
    add("Berkas sumber", str(text_db.path))
    add("Ukuran", "%d byte" % len(text_db.raw))
    add("SHA-256", text_db.sha256)
    add("Jumlah entri", text_db.count)
    add("table_start", "0x%06X" % text_db.table_start)
    add("base", "0x%06X" % text_db.base)
    add("delta hdr[1]", text_db.hdr1_delta)
    add("", "")
    if label_db is not None:
        add("Berkas label", str(label_db.path))
        add("SHA-256 label", label_db.sha256)
        add("Jumlah entri label", label_db.count)
    else:
        add("Berkas label", "(tidak dipakai, kolom Label kosong)")
    add("", "")
    add("Baris ditulis", row_count)


__all__ = ["ExportResult", "export", "resolve_output", "default_output"]