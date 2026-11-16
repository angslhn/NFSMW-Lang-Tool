"""NFSMW Lang Tool -- ekspor dan impor basis data string NFSMW.

Letak berkas
------------
Semua berkas kerja berada di folder ``files``, di samping ``main.py``::

    NFSMW Lang Tool/
    ├── main.py
    ├── README.md
    ├── requirements.txt
    └── files/
        ├── English.bin      sumber  (taruh di sini)
        ├── Labels.bin       pendamping (taruh di sini)
        ├── English.xlsx     hasil export
        ├── English.txt      teks saja: index, text
        ├── English_new.bin  hasil import / tambah / hapus string
        └── Labels_new.bin   hasil tambah / hapus label

``English.bin`` dan ``Labels.bin`` adalah sepasang. ``English.bin`` berisi
teks, ``Labels.bin`` berisi nama simbol untuk tiap ``Key``. Tanpa
``Labels.bin`` tool tetap jalan, tetapi kolom ``Label`` kosong semua dan
hanya kolom ``Text`` yang bisa dipakai menebak konteks.

Jalankan tanpa argumen untuk masuk menu interaktif::

    python main.py

Atau langsung lewat argumen::

    python main.py export
    python main.py import English.xlsx
    python main.py to-txt English.xlsx
    python main.py from-txt English.txt --base English.xlsx
    python main.py add-string --label MY_STRING --text "Teks baru"
    python main.py remove-string --key 0x1234ABCD
    python main.py info English_new.bin
    python main.py verify "*.bin"

Nama berkas tanpa folder dianggap relatif terhadap ``files``. Path lengkap
atau path dengan folder (``D:\\kerja\\English.bin``) dipakai apa adanya.

Fungsi utama ada di paket :mod:`lib`:

- :mod:`lib.nfsbin`    baca/tulis struktur berkas ``.bin``
- :mod:`lib.nfstable`  definisi empat kolom dan pembacaan tabel
- :mod:`lib.nfsexport` ekspor ``.bin`` -> ``.xlsx``/``.csv``
- :mod:`lib.nfsimport` impor ``.xlsx``/``.csv`` -> ``.bin``
- :mod:`lib.nfstxt`    jembatan tabel <-> ``.txt`` berformat ``index, text``
- :mod:`lib.nfsadd`    tambah string baru (key + label + text)
- :mod:`lib.nfsremove` hapus string lama berdasarkan key
- :mod:`lib.tui`       tampilan terminal dan pembacaan masukan

Tool ini hanya memindahkan data. Tidak ada pemrosesan isi teks di dalamnya.
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import nfsbin          # noqa: E402
import nfsadd          # noqa: E402
import nfsremove       # noqa: E402
import nfsexport       # noqa: E402
import nfsimport       # noqa: E402
import nfstable        # noqa: E402
import nfstxt          # noqa: E402
import tui             # noqa: E402

#: Folder kerja baku: berkas .bin ditaruh di sini, hasil juga ditulis di sini.
FILES_DIR = HERE / "files"

DEFAULT_BIN = "English.bin"
DEFAULT_LABELS = "Labels.bin"

APP_NAME = "NFSMW Lang Tool"
VERSION = "1.0"
AUTHOR = "Aang Solihin"


# ---------------------------------------------------------------- bantuan


def _num(value: int) -> str:
    return "{:,}".format(value)


def _ensure_files_dir() -> Path:
    """Pastikan folder ``files`` ada, lalu kembalikan path-nya."""
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    return FILES_DIR


def _input_path(value: str | Path | None) -> Path | None:
    """Tentukan berkas masukan.

    Urutan pencarian: apa adanya, lalu di dalam ``files``. Nilai yang tidak
    ditemukan dikembalikan apa adanya agar pesan errornya sesuai yang diketik.
    """
    if value is None:
        return None
    text = str(value).strip().strip('"')
    if not text:
        return None
    p = Path(text)
    if p.is_absolute() or p.exists():
        return p
    candidate = FILES_DIR / p
    return candidate if candidate.exists() else p


def _output_path(value: str | Path | None, default_name: str) -> Path:
    """Tentukan berkas hasil.

    Kosong            -> ``files/<default_name>``
    nama saja         -> ``files/<nama>``
    ada folder / absolut -> dipakai apa adanya
    """
    if value is None or not str(value).strip():
        return FILES_DIR / default_name
    p = Path(str(value).strip().strip('"'))
    if p.is_absolute():
        return p
    if p.parent != Path("."):
        return p
    return FILES_DIR / p


def _expand(pattern: str) -> list[Path]:
    """Kembangkan argumen berkas menjadi daftar path.

    Urutan: path langsung, lalu isi folder ``files``, lalu pola glob di folder
    ``files``, terakhir glob di folder kerja. Folder ``files`` didahulukan
    supaya ``"*.bin"`` tidak tertangkap berkas lain di folder kerja.
    """
    p = Path(pattern)
    if p.exists():
        return [p]

    inside = FILES_DIR / p
    if inside.exists():
        return [inside]

    if any(c in pattern for c in "*?["):
        found = sorted(Path(m) for m in glob.glob(str(FILES_DIR / pattern)))
        if found:
            return found
        return sorted(Path(m) for m in glob.glob(pattern))

    return [p]


def _bins_in_files() -> list[Path]:
    return sorted(FILES_DIR.glob("*.bin"))


def _tables_in_files() -> list[Path]:
    found: list[Path] = []
    for pattern in ("*.xlsx", "*.xlsm", "*.csv", "*.tsv"):
        found += sorted(FILES_DIR.glob(pattern))
    return found


def _txt_in_files() -> list[Path]:
    return sorted(FILES_DIR.glob("*.txt"))


def _names(paths: list[Path]) -> list[str]:
    return [p.name for p in paths]


def _not_found(path: Path) -> int:
    """Pesan baku saat berkas masukan tidak ditemukan."""
    tui.err("Tidak ditemukan: %s" % path)
    tui.note("Folder berkas: %s" % FILES_DIR)
    groups = [
        (".bin", _bins_in_files()),
        ("tabel", _tables_in_files()),
        ("txt", _txt_in_files()),
    ]
    shown = False
    for label, items in groups:
        if not items:
            continue
        tui.note("%-5s: %s" % (label, ", ".join(_names(items))))
        shown = True
    if not shown:
        tui.note("Folder itu masih kosong. Taruh English.bin dan Labels.bin di sana.")
    return 2


def _auto_labels() -> Path | None:
    """Pakai ``files/Labels.bin`` bila ada."""
    candidate = FILES_DIR / DEFAULT_LABELS
    return candidate if candidate.exists() else None


def _default_table_name() -> str | None:
    """Tabel pertama yang ada di ``files``, untuk nilai baku menu."""
    for pattern in ("*.xlsx", "*.xlsm", "*.csv"):
        found = sorted(FILES_DIR.glob(pattern))
        if found:
            return found[0].name
    return None


def _default_bin_name() -> str:
    """Berkas ``.bin`` pertama di ``files``, selain berkas label."""
    for path in _bins_in_files():
        if path.name.lower() != DEFAULT_LABELS.lower():
            return path.name
    return DEFAULT_BIN


def _default_txt_name() -> str | None:
    """Berkas ``.txt`` pertama di ``files``, untuk nilai baku menu."""
    found = _txt_in_files()
    return found[0].name if found else None


def _as_txt_name(value: str) -> str:
    """Pastikan nama berkas txt berakhiran ``.txt``."""
    text = value.strip().strip('"')
    if text and Path(text).suffix.lower() != ".txt":
        text += ".txt"
    return text


# ---------------------------------------------------------------- operasi


def run_export(
    bin_path: str | Path | None,
    label_path: str | Path | None = None,
    fmt: str = "xlsx",
    out_path: str | Path | None = None,
) -> int:
    """Ekspor ``.bin`` -> tabel. Hasil baku di ``files/``."""
    _ensure_files_dir()

    source = _input_path(bin_path) if bin_path else FILES_DIR / DEFAULT_BIN
    if source is None or not source.exists():
        return _not_found(source or FILES_DIR / DEFAULT_BIN)

    if label_path:
        labels = _input_path(label_path)
        if labels is None or not labels.exists():
            tui.warn("Berkas label tidak ditemukan, kolom Label akan kosong.")
            labels = None
    else:
        labels = _auto_labels()
        if labels is None:
            tui.warn("%s tidak ada di folder files, kolom Label akan kosong."
                     % DEFAULT_LABELS)

    suffix = ".csv" if fmt.lower() == "csv" else ".xlsx"
    out = _output_path(out_path, Path(source).stem + suffix)

    result = nfsexport.export(
        bin_path=source,
        out_path=out,
        label_path=labels,
        fmt=fmt,
    )
    tui.kv([
        ("Sumber", result.source),
        ("Label", result.label_source or "(tidak dipakai)"),
        ("Hasil", result.output),
    ])
    print()
    tui.kv([
        ("Baris", _num(result.rows)),
        ("Berlabel", _num(result.labeled)),
        ("Tanpa label", _num(result.rows - result.labeled)),
    ])
    return 0


def run_import(
    table_path: str | Path,
    bin_path: str | Path | None = None,
    out_path: str | Path | None = None,
    *,
    force: bool = False,
) -> int:
    """Impor tabel -> ``.bin``. Hasil baku di ``files/``."""
    _ensure_files_dir()

    table = _input_path(table_path)
    if table is None or not table.exists():
        return _not_found(table or Path(str(table_path)))

    source = _input_path(bin_path) if bin_path else FILES_DIR / DEFAULT_BIN
    if source is None or not source.exists():
        return _not_found(source or FILES_DIR / DEFAULT_BIN)

    out = _output_path(out_path, Path(table).stem + "_new.bin")

    try:
        report = nfsimport.import_table(table, source, out, strict=not force)
    except nfsimport.ImportRejected as exc:
        tui.err(str(exc))
        tui.note("Gunakan --force untuk tetap menulis hasil meski ada error.")
        return 2

    _print_report(report)
    ok = report.verified and not report.errors
    if ok:
        print()
        tui.ok("Berkas siap dipakai: %s" % out)
        tui.note("Salin ke LANGUAGES\\%s (cadangkan yang asli dulu)."
                 % Path(source).name)
    return 0 if ok else 1


def _print_report(report) -> None:
    """Ringkasan impor dalam bentuk yang mudah dibaca."""
    tui.kv([
        ("Sumber", report.source),
        ("Tabel", report.table),
        ("Hasil", report.output or "(hanya periksa)"),
    ])
    print()
    tui.kv([
        ("Entri", _num(report.total_entries)),
        ("Berubah", _num(report.changed)),
        ("Tetap", _num(report.unchanged)),
    ])
    if report.missing_rows:
        tui.kv([("Baris tabel tidak dipakai", _num(report.missing_rows))])

    if report.warnings:
        print()
        tui.section("Peringatan (%d)" % len(report.warnings))
        for item in report.warnings[:10]:
            tui.warn(item.message)
        if len(report.warnings) > 10:
            tui.note("... dan %d peringatan lain" % (len(report.warnings) - 10))

    if report.errors:
        print()
        tui.section("Error (%d)" % len(report.errors))
        for item in report.errors[:15]:
            tui.err("index %s: %s" % (item.index, item.message))
        if len(report.errors) > 15:
            tui.note("... dan %d error lain" % (len(report.errors) - 15))


def run_info(bin_path: str | Path | None) -> int:
    """Tampilkan struktur satu berkas ``.bin``."""
    _ensure_files_dir()
    path = _input_path(bin_path) if bin_path else FILES_DIR / DEFAULT_BIN
    if path is None or not path.exists():
        return _not_found(path or FILES_DIR / DEFAULT_BIN)

    db = nfsbin.parse(path)
    head = nfsbin.inspect_header(db.raw)

    tui.kv([
        ("Berkas", db.path),
        ("Ukuran", "%s byte" % _num(len(db.raw))),
        ("SHA-256", db.sha256),
    ])
    print()
    tui.section("Header")
    tui.kv([
        ("[0]", "0x%08X  ID blok STRBlocks" % head["hdr0"]),
        ("[1]", "0x%08X  akhir blob string" % head["hdr1"]),
        ("[2]", "0x%08X  konstanta" % head["konstanta"]),
        ("[3]", "%s  entri" % _num(head["count"])),
        ("[4]", "0x%08X  penunjuk blok tabel" % head["table_ptr"]),
        ("[5]", "0x%08X  entri terakhir (base - 8)" % head["last_entry"]),
    ])
    print()
    tui.section("Tata letak")
    tui.kv([
        ("tabel", "0x%06X .. 0x%06X" % (db.table_start, db.table_start + 8 * db.count)),
        ("blob", "0x%06X .. 0x%06X" % (db.base, db.blob_end)),
        ("ekor", "0x%06X .. 0x%06X (%s byte)"
                 % (db.blob_end, len(db.raw), _num(len(db.tail)))),
    ])
    print()

    problems = db.problems()
    if problems:
        tui.section("Masalah")
        for problem in problems:
            tui.err(problem)
    else:
        tui.ok("Struktur sehat")
    for warning in db.warnings:
        tui.warn(warning)
    return 0 if not problems else 1


def run_verify(patterns: list[str]) -> int:
    """Uji round-trip satu atau beberapa berkas ``.bin``."""
    _ensure_files_dir()
    all_ok = True
    failures = 0
    total = 0

    for pattern in patterns:
        for path in _expand(pattern):
            if not path.exists():
                tui.warn("%s tidak ada" % path.name)
                all_ok = False
                continue
            total += 1
            try:
                good, msg = nfsbin.verify_roundtrip(path)
            except Exception as exc:  # noqa: BLE001
                tui.err("%-26s %s" % (path.name, exc))
                all_ok = False
                failures += 1
                continue
            if good:
                tui.ok("%-26s identik (%s byte)" % (path.name, _num(len(path.read_bytes()))))
            else:
                tui.err("%-26s %s" % (path.name, msg))
                failures += 1
                all_ok = False

    print()
    if all_ok:
        tui.ok("%d berkas diperiksa, semua identik" % total)
    else:
        tui.err("%d berkas diperiksa, %d gagal" % (total, failures))
    return 0 if all_ok else 1


def run_check(table_path: str | Path, bin_path: str | Path | None) -> int:
    """Validasi tabel tanpa menulis berkas apa pun."""
    _ensure_files_dir()
    table = _input_path(table_path)
    if table is None or not table.exists():
        return _not_found(table or Path(str(table_path)))
    source = _input_path(bin_path) if bin_path else FILES_DIR / DEFAULT_BIN
    if source is None or not source.exists():
        return _not_found(source or FILES_DIR / DEFAULT_BIN)

    report = nfsimport.check(table, source)
    _print_report(report)
    print()
    if report.errors:
        tui.err("Tabel bermasalah, jangan diimpor.")
    else:
        tui.ok("Tabel siap diimpor.")
    return 0 if not report.errors else 1


def run_to_txt(
    table_path: str | Path,
    out_path: str | Path | None = None,
) -> int:
    """Ambil ``Index`` dan ``Text`` dari tabel, tulis menjadi ``.txt``."""
    _ensure_files_dir()
    table = _input_path(table_path)
    if table is None or not table.exists():
        return _not_found(table or Path(str(table_path)))

    default_name = Path(table).stem + ".txt"
    out = _output_path(out_path, default_name)

    try:
        result = nfstxt.write_txt(table, out)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        tui.err(str(exc))
        return 2

    tui.kv([
        ("Tabel", result.source),
        ("TXT", result.output),
    ])
    print()
    tui.kv([("Baris", _num(result.rows))])
    print()
    tui.ok("Teks siap diedit: %s" % result.output)
    tui.note("Format tiap baris: index, text")
    return 0


def run_from_txt(
    txt_path: str | Path,
    base_table: str | Path,
    out_path: str | Path | None = None,
) -> int:
    """Tulis tabel baru: kerangka dari tabel dasar, ``Text`` dari ``.txt``."""
    _ensure_files_dir()
    txt = _input_path(txt_path)
    if txt is None or not txt.exists():
        return _not_found(txt or Path(str(txt_path)))
    base = _input_path(base_table)
    if base is None or not base.exists():
        return _not_found(base or Path(str(base_table)))

    default_out = Path(txt).stem + "_new" + Path(base).suffix
    out = _output_path(out_path, default_out)

    try:
        result = nfstxt.build_from_txt(txt, base, out)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        tui.err(str(exc))
        return 2

    tui.kv([
        ("TXT", result.txt),
        ("Tabel dasar", result.base),
        ("Hasil", result.output),
    ])
    print()
    tui.kv([
        ("Baris", _num(result.rows)),
        ("Teks diganti", _num(result.applied)),
        ("Tetap dari dasar", _num(result.unchanged)),
    ])

    if result.missing:
        print()
        shown = ", ".join(str(i) for i in result.missing[:10])
        if len(result.missing) > 10:
            shown += ", ..."
        tui.warn("%s Index tidak ada di txt, teksnya diambil dari tabel dasar."
                 % _num(len(result.missing)))
        tui.note("Index: %s" % shown)

    print()
    tui.ok("Tabel baru siap: %s" % result.output)
    tui.note("Lanjutkan lewat menu Import bila ingin menjadi .bin.")
    return 0


def _new_key(key_text: str | None, label: str) -> int:
    """Tentukan key baru: eksplisit, atau hash dari label."""
    text = "" if key_text is None else str(key_text).strip()
    if text.lower() in ("", "auto"):
        if not label:
            raise ValueError("Isi Label atau Key terlebih dahulu.")
        key = nfsbin.binhash(label)
        if key == 0:
            raise ValueError("Label tidak menghasilkan key yang sah.")
        return key

    key = nfstable.parse_key(text)
    if key is None:
        raise ValueError(
            "Key '%s' tidak dapat dibaca. Tulis heksadesimal, mis. 0x1234ABCD."
            % text
        )
    if not 0 < key <= 0xFFFFFFFF:
        raise ValueError("Key 0x%X di luar rentang u32." % key)
    return key


def run_add_string(
    bin_path: str | Path | None,
    key_text: str | None,
    label: str | None,
    text: str | None,
    out_path: str | Path | None = None,
    labels_path: str | Path | None = None,
    labels_out: str | Path | None = None,
    *,
    escapes: bool = False,
) -> int:
    """Tambah satu string baru ke ``.bin`` dan tulis berkas baru."""
    _ensure_files_dir()

    source = _input_path(bin_path) if bin_path else FILES_DIR / DEFAULT_BIN
    if source is None or not source.exists():
        return _not_found(source or FILES_DIR / DEFAULT_BIN)

    label = "" if label is None else str(label).strip()
    value = "" if text is None else str(text)
    if escapes:
        value = nfsadd.decode_escapes(value)

    try:
        key = _new_key(key_text, label)
    except ValueError as exc:
        tui.err(str(exc))
        return 2

    try:
        payload = value.encode(nfsbin.ENCODING)
    except UnicodeEncodeError as exc:
        tui.err("Teks tidak dapat diwakili encoding %s." % nfsbin.ENCODING)
        tui.note("Karakter bermasalah ada di posisi %d." % exc.start)
        return 2
    if b"\x00" in payload:
        tui.err("Teks mengandung byte NUL, tidak bisa disimpan.")
        return 2

    db = nfsbin.parse(source)
    if key in set(db.keys):
        tui.err("Key 0x%08X sudah ada di %s." % (key, source.name))
        tui.note("String yang sudah ada diubah lewat alur Export/Import.")
        return 2

    labels = _input_path(labels_path) if labels_path else None
    if labels is not None and not labels.exists():
        tui.warn("%s tidak ditemukan, label tidak ditulis ke Labels.bin." % labels)
        labels = None
    if labels is not None and labels.resolve() == source.resolve():
        tui.err("Berkas Labels.bin tidak boleh sama dengan berkas bahasa.")
        return 2

    out = _output_path(
        out_path, Path(source).stem + "_new.bin"
    )
    if out.resolve() == Path(source).resolve():
        tui.err("Hasil tidak boleh menimpa berkas sumber.")
        return 2

    try:
        report = nfsadd.add_strings(
            source,
            [(key, label, payload)],
            out,
            labels_path=labels,
            labels_out=labels_out,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        tui.err(str(exc))
        return 2

    _print_add_report(report)
    if not report.verified or report.problems:
        return 1

    print()
    tui.ok("Berkas siap dipakai: %s" % out)
    tui.note("Salin ke LANGUAGES\\%s (cadangkan yang asli dulu)."
             % Path(source).name)
    if label and report.label_output is None:
        tui.note("Label '%s' hanya untuk laporan; tambahkan Labels.bin agar "
                 "muncul saat Export." % label)
    return 0


def _print_add_report(report: nfsadd.AddReport) -> None:
    tui.kv([
        ("Sumber", report.source),
        ("Hasil", report.output or "(tidak ditulis)"),
    ])
    print()
    tui.kv([
        ("Entri awal", _num(report.total_before)),
        ("Ditambah", _num(report.added)),
        ("Entri akhir", _num(report.total_after)),
    ])

    print()
    tui.section("String baru")
    for key, label, payload in report.additions:
        text = nfstxt.escape_text(payload.decode(nfsbin.ENCODING))
        tui.kv([
            ("Key", "0x%08X" % key),
            ("Label", label or "(kosong)"),
            ("Teks", text),
        ])

    if report.label_source is not None:
        print()
        tui.section("Berkas label")
        tui.kv([
            ("Sumber", report.label_source),
            ("Hasil", report.label_output or "(tidak ditulis)"),
            ("Label baru", _num(report.labels_added)),
            ("Total label", _num(report.labels_total)),
        ])
        for key, label in report.labels_skipped:
            tui.warn("Key 0x%08X sudah punya label '%s', tidak diubah."
                     % (key, label))

    print()
    if report.problems:
        tui.section("Error (%d)" % len(report.problems))
        for problem in report.problems[:15]:
            tui.err(problem)
        if len(report.problems) > 15:
            tui.note("... dan %d error lain" % (len(report.problems) - 15))
    else:
        tui.ok("Verifikasi: LOLOS (key dan teks lama tidak berubah)")


def run_remove_string(
    bin_path: str | Path | None,
    key_texts: str | list[str],
    out_path: str | Path | None = None,
    labels_path: str | Path | None = None,
    labels_out: str | Path | None = None,
) -> int:
    """Hapus satu atau beberapa string dari ``.bin`` dan tulis berkas baru."""
    _ensure_files_dir()

    source = _input_path(bin_path) if bin_path else FILES_DIR / DEFAULT_BIN
    if source is None or not source.exists():
        return _not_found(source or FILES_DIR / DEFAULT_BIN)

    raw_keys = [key_texts] if isinstance(key_texts, str) else list(key_texts)
    keys: list[int] = []
    for text in raw_keys:
        value = str(text).strip()
        if not value:
            continue
        key = nfstable.parse_key(value)
        if key is None:
            tui.err(
                "Key '%s' tidak dapat dibaca. Tulis heksadesimal, mis. "
                "0x1234ABCD." % value
            )
            return 2
        if not 0 < key <= 0xFFFFFFFF:
            tui.err("Key 0x%X di luar rentang u32." % key)
            return 2
        keys.append(key)

    if not keys:
        tui.err("Isi minimal satu Key yang akan dihapus.")
        return 2
    if len(set(keys)) != len(keys):
        tui.err("Key yang sama muncul lebih dari sekali.")
        return 2

    db = nfsbin.parse(source)
    existing = set(db.keys)
    missing = [key for key in keys if key not in existing]
    if missing:
        tui.err(
            "Key %s tidak ada di %s."
            % (", ".join("0x%08X" % key for key in missing[:5]), source.name)
        )
        tui.note("Lihat kolom Key pada tabel hasil Export.")
        return 2

    labels = _input_path(labels_path) if labels_path else None
    if labels is not None and not labels.exists():
        tui.warn("%s tidak ditemukan, label tidak diubah." % labels)
        labels = None
    if labels is not None and labels.resolve() == source.resolve():
        tui.err("Berkas Labels.bin tidak boleh sama dengan berkas bahasa.")
        return 2

    out = _output_path(out_path, Path(source).stem + "_new.bin")
    if out.resolve() == Path(source).resolve():
        tui.err("Hasil tidak boleh menimpa berkas sumber.")
        return 2

    try:
        report = nfsremove.remove_strings(
            source,
            keys,
            out,
            labels_path=labels,
            labels_out=labels_out,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        tui.err(str(exc))
        return 2

    _print_remove_report(report)
    if not report.verified or report.problems:
        return 1

    print()
    tui.ok("Berkas siap dipakai: %s" % out)
    tui.note("Salin ke LANGUAGES\\%s (cadangkan yang asli dulu)."
             % Path(source).name)
    if report.label_source is None and labels_path:
        tui.note("Labels.bin tidak diubah.")
    return 0


def _print_remove_report(report: nfsremove.RemoveReport) -> None:
    tui.kv([
        ("Sumber", report.source),
        ("Hasil", report.output or "(tidak ditulis)"),
    ])
    print()
    tui.kv([
        ("Entri awal", _num(report.total_before)),
        ("Dihapus", _num(report.removed_count)),
        ("Entri akhir", _num(report.total_after)),
    ])

    print()
    tui.section("String dihapus")
    for key, payload in report.removed:
        text = nfstxt.escape_text(payload.decode(nfsbin.ENCODING))
        tui.kv([
            ("Key", "0x%08X" % key),
            ("Teks", text),
        ])

    if report.label_source is not None:
        print()
        tui.section("Berkas label")
        tui.kv([
            ("Sumber", report.label_source),
            ("Hasil", report.label_output or "(tidak ditulis)"),
            ("Label dihapus", _num(len(report.labels_removed))),
            ("Total label", _num(report.labels_total)),
        ])
        for key, label in report.labels_removed:
            tui.kv([
                ("Key", "0x%08X" % key),
                ("Label", label),
            ])
        for key in report.labels_missing:
            tui.note("Key 0x%08X tidak punya label di Labels.bin." % key)

    print()
    if report.problems:
        tui.section("Error (%d)" % len(report.problems))
        for problem in report.problems[:15]:
            tui.err(problem)
        if len(report.problems) > 15:
            tui.note("... dan %d error lain" % (len(report.problems) - 15))
    else:
        tui.ok("Verifikasi: LOLOS (key dan teks tersisa tidak berubah)")


# ---------------------------------------------------------------- perintah CLI


def cmd_export(args) -> int:
    return run_export(args.bin, args.labels, args.format, args.output)


def cmd_import(args) -> int:
    return run_import(args.table, args.bin, args.output, force=args.force)


def cmd_info(args) -> int:
    return run_info(args.bin)


def cmd_verify(args) -> int:
    return run_verify(args.bins)


def cmd_check(args) -> int:
    return run_check(args.table, args.bin)


def cmd_to_txt(args) -> int:
    return run_to_txt(args.table, args.output)


def cmd_from_txt(args) -> int:
    return run_from_txt(args.txt, args.base, args.output)


def cmd_add_string(args) -> int:
    return run_add_string(
        args.bin,
        args.key,
        args.label,
        args.text,
        args.output,
        args.labels,
        args.labels_out,
        escapes=args.escape,
    )


def cmd_remove_string(args) -> int:
    return run_remove_string(
        args.bin,
        args.keys,
        args.output,
        args.labels,
        args.labels_out,
    )


# ---------------------------------------------------------------- menu


def menu() -> int:
    # Layar bersih sekali saat masuk. Setelah tiap aksi, ``tui.pause()`` yang
    # membersihkan layar sebelum menu digambar ulang.
    tui.clear()
    while True:
        tui.banner(VERSION, AUTHOR, str(FILES_DIR))
        _show_files()
        _show_info()
        choice = tui.menu(
            [
                "Export",
                "Import",
                "Ke TXT",
                "Dari TXT",
                "Tambah String",
                "Hapus String",
                "Info",
                "Verify",
                "Buka folder files",
                "Keluar",
            ],
            title="Menu Utama",
            label="Pilih",
        )

        if choice in (0, 10):
            tui.abort("Sampai jumpa.")
            return 0

        if choice == 1:
            _menu_export()
        elif choice == 2:
            _menu_import()
        elif choice == 3:
            _menu_to_txt()
        elif choice == 4:
            _menu_from_txt()
        elif choice == 5:
            _menu_add_string()
        elif choice == 6:
            _menu_remove_string()
        elif choice == 7:
            _menu_info()
        elif choice == 8:
            _menu_verify()
        elif choice == 9:
            _menu_open_files()
        tui.pause()


def _show_files() -> None:
    """Ringkas isi folder ``files`` di bawah banner."""
    _ensure_files_dir()
    bins = _bins_in_files()
    tables = _tables_in_files()
    tui.section("Folder files")

    if bins:
        for path in bins:
            size = "%s byte" % _num(path.stat().st_size)
            print("    %s %s" % (tui.style("bin  ", "green"),
                                 path.name.ljust(22) + tui.style(size, "gray")))
    else:
        print("    " + tui.style("belum ada berkas .bin", "yellow"))

    if tables:
        for path in tables:
            size = "%s byte" % _num(path.stat().st_size)
            print("    %s %s" % (tui.style("tabel", "cyan"),
                                 path.name.ljust(22) + tui.style(size, "gray")))
    else:
        print("    " + tui.style("belum ada tabel hasil export", "gray"))

    txts = _txt_in_files()
    if txts:
        for path in txts:
            size = "%s byte" % _num(path.stat().st_size)
            print("    %s %s" % (tui.style("txt  ", "magenta"),
                                 path.name.ljust(22) + tui.style(size, "gray")))
    else:
        print("    " + tui.style("belum ada berkas .txt", "gray"))

    if not _auto_labels() and bins:
        print()
        tui.warn("%s tidak ada, kolom Label akan kosong." % DEFAULT_LABELS)
    print()


def _show_info() -> None:
    """Keterangan singkat arti tiap menu."""
    tui.section("Info")
    tui.bullets([
        ("Export", ".bin menjadi tabel (.xlsx/.csv) berisi 4 kolom, "
                   "siap diedit di Excel"),
        ("Import", "tabel yang sudah diedit dikembalikan menjadi .bin baru"),
        ("Ke TXT", "pilih tabel, lalu tulis teksnya saja ke .txt "
                   "(tiap baris: index, text)"),
        ("Dari TXT", "pilih .txt dan tabel dasar, lalu tulis tabel baru "
                     "dengan teks dari .txt"),
        ("Tambah String", "tambah satu key + label + text baru ke .bin"),
        ("Hapus String", "hapus satu atau beberapa key dari .bin"),
        ("Info", "lihat header dan tata letak satu berkas .bin"),
        ("Verify", "uji bahwa berkas .bin dibaca dan ditulis ulang persis sama"),
    ])
    print()
    print("  " + tui.style("Kolom tabel: Index, Key, Label, Text. "
                           "Ubah hanya kolom Text.", "gray"))
    print()


def _menu_export() -> None:
    tui.screen("Export  (.bin -> tabel)")
    bins = _bins_in_files()
    if not bins:
        tui.err("Tidak ada berkas .bin di folder files.")
        tui.note("Taruh English.bin (dan Labels.bin) di %s" % FILES_DIR)
        return

    tui.section("Berkas sumber")
    default_bin = _default_bin_name()
    bin_name = tui.pick(_names(bins), "Berkas .bin", default_bin)
    bin_path = _input_path(bin_name)
    if bin_path is None or not bin_path.exists():
        _not_found(bin_path or FILES_DIR / bin_name)
        return

    print()
    label_path: Path | None = None
    if _auto_labels():
        if tui.confirm("Pakai %s untuk kolom Label" % DEFAULT_LABELS, True):
            label_path = _auto_labels()
    else:
        tui.warn("%s tidak ada di folder files." % DEFAULT_LABELS)
        answer = tui.ask("Berkas label (kosongkan bila tidak ada)", "")
        label_path = _input_path(answer) if answer else None

    if label_path is not None and not label_path.exists():
        tui.warn("Berkas label tidak ditemukan, kolom Label akan kosong.")
        label_path = None

    print()
    tui.section("Format hasil")
    fmt = tui.pick(["Excel (.xlsx)", "CSV (.csv)"], "Format", "Excel (.xlsx)")
    fmt_name = "csv" if fmt.lower().startswith("c") else "xlsx"

    print()
    default_out = Path(bin_path).stem + "." + fmt_name
    out = tui.ask("Nama berkas hasil", default_out)

    print()
    tui.rule()
    code = run_export(bin_path, label_path, fmt_name, out)
    if code == 0:
        print()
        tui.ok("Selesai.")


def _menu_import() -> None:
    tui.screen("Import  (tabel -> .bin)")
    tables = _tables_in_files()
    if not tables:
        tui.err("Tidak ada tabel di folder files.")
        tui.note("Jalankan Export dulu untuk membuat English.xlsx.")
        return

    tui.section("Berkas tabel")
    table_name = tui.pick(_names(tables), "Tabel", _default_table_name())
    table = _input_path(table_name)
    if table is None or not table.exists():
        _not_found(table or FILES_DIR / table_name)
        return

    print()
    tui.section("Berkas .bin sumber")
    bins = _bins_in_files()
    if bins:
        default_bin = _default_bin_name()
        bin_name = tui.pick(_names(bins), "Berkas .bin", default_bin)
        bin_path = _input_path(bin_name)
    else:
        bin_path = _input_path(tui.ask("Berkas .bin", DEFAULT_BIN))
    if bin_path is None or not bin_path.exists():
        _not_found(bin_path or FILES_DIR / DEFAULT_BIN)
        return

    print()
    default_out = table.stem + "_new.bin"
    out = tui.ask("Nama berkas hasil", default_out)

    print()
    if not tui.confirm("Lanjutkan", True):
        tui.abort("Dibatalkan.")
        return

    print()
    code = run_import(table, bin_path, out)
    if code == 0:
        print()
        tui.ok("Selesai.")


def _menu_to_txt() -> None:
    tui.screen("Ke TXT  (tabel -> txt)")
    tables = _tables_in_files()
    if not tables:
        tui.err("Belum ada tabel .xlsx/.csv di folder files.")
        tui.note("Jalankan Export dulu untuk membuat English.xlsx.")
        return

    tui.section("1. Tabel sumber")
    table_name = tui.pick(_names(tables), "Tabel", _default_table_name())
    table = _input_path(table_name)
    if table is None or not table.exists():
        _not_found(table or FILES_DIR / table_name)
        return

    print()
    tui.section("2. Berkas txt")
    default_txt = Path(table).stem + ".txt"
    txt_name = _as_txt_name(tui.ask("Nama berkas .txt", default_txt))
    txt = _output_path(txt_name, default_txt)
    if txt.exists():
        print()
        if not tui.confirm("%s sudah ada, timpa" % txt.name, False):
            tui.abort("Dibatalkan.")
            return

    print()
    tui.rule()
    code = run_to_txt(table, txt)
    if code == 0:
        print()
        tui.ok("Selesai.")


def _menu_from_txt() -> None:
    tui.screen("Dari TXT  (txt -> tabel)")
    tables = _tables_in_files()
    if not tables:
        tui.err("Belum ada tabel .xlsx/.csv di folder files.")
        tui.note("Alur ini butuh tabel dasar: jalankan Export dulu.")
        return

    tui.section("1. Berkas txt")
    txts = _txt_in_files()
    if txts:
        txt_name = tui.pick(_names(txts), "Berkas .txt", _default_txt_name())
    else:
        tui.warn("Belum ada .txt di folder files.")
        txt_name = _as_txt_name(tui.ask("Berkas .txt (nama atau path)", ""))
        if not txt_name:
            tui.abort("Dibatalkan.")
            return
    txt = _input_path(txt_name)
    if txt is None or not txt.exists():
        _not_found(txt or FILES_DIR / str(txt_name))
        return

    print()
    tui.section("2. Tabel dasar")
    table_name = tui.pick(_names(tables), "Tabel dasar", _default_table_name())
    base = _input_path(table_name)
    if base is None or not base.exists():
        _not_found(base or FILES_DIR / table_name)
        return

    print()
    default_out = Path(txt).stem + "_new" + base.suffix
    out = tui.ask("Nama berkas hasil", default_out)

    print()
    if not tui.confirm("Lanjutkan", True):
        tui.abort("Dibatalkan.")
        return

    print()
    code = run_from_txt(txt, base, out)
    if code == 0:
        print()
        tui.ok("Selesai.")


def _menu_add_string() -> None:
    tui.screen("Tambah String  (.bin -> .bin)")
    bins = _bins_in_files()
    if not bins:
        tui.err("Tidak ada berkas .bin di folder files.")
        return

    tui.section("1. Berkas .bin")
    bin_name = tui.pick(_names(bins), "Berkas .bin", _default_bin_name())
    source = _input_path(bin_name)
    if source is None or not source.exists():
        _not_found(source or FILES_DIR / bin_name)
        return

    print()
    tui.section("2. Data string")
    label = tui.ask_optional("Label (boleh kosong)")
    key_text = tui.ask_optional(
        "Key (0x..., auto = hash label)", "auto" if label else None
    )

    try:
        key = _new_key(key_text, label)
    except ValueError as exc:
        tui.err(str(exc))
        return

    db = nfsbin.parse(source)
    if key in set(db.keys):
        tui.err("Key 0x%08X sudah ada di %s." % (key, source.name))
        tui.note("String yang sudah ada diubah lewat alur Export/Import.")
        return

    print()
    tui.kv([
        ("Key", "0x%08X" % key),
        ("Label", label or "(kosong)"),
    ])
    print()
    text = tui.ask_text("Teks (\\xHH untuk byte kontrol)")
    try:
        payload = text.encode(nfsbin.ENCODING)
    except UnicodeEncodeError as exc:
        tui.err("Teks tidak dapat diwakili encoding %s." % nfsbin.ENCODING)
        tui.note("Karakter bermasalah ada di posisi %d." % exc.start)
        return
    if b"\x00" in payload:
        tui.err("Teks mengandung byte NUL, tidak bisa disimpan.")
        return

    print()
    default_out = Path(source).stem + "_new.bin"
    out = tui.ask("Nama berkas hasil", default_out)

    labels: Path | None = None
    if label:
        auto = _auto_labels()
        if auto is not None and auto.resolve() != Path(source).resolve():
            print()
            if tui.confirm("Tambahkan label ke salinan %s" % DEFAULT_LABELS, True):
                labels = auto
        elif auto is None:
            print()
            tui.note("Labels.bin tidak ada; label hanya untuk laporan.")

    print()
    if not tui.confirm("Lanjutkan", True):
        tui.abort("Dibatalkan.")
        return

    print()
    tui.rule()
    code = run_add_string(
        source, "0x%08X" % key, label, text, out, labels, None, escapes=True
    )
    if code == 0:
        print()
        tui.ok("Selesai.")


def _menu_remove_string() -> None:
    tui.screen("Hapus String  (.bin -> .bin)")
    bins = _bins_in_files()
    if not bins:
        tui.err("Tidak ada berkas .bin di folder files.")
        return

    tui.section("1. Berkas .bin")
    bin_name = tui.pick(_names(bins), "Berkas .bin", _default_bin_name())
    source = _input_path(bin_name)
    if source is None or not source.exists():
        _not_found(source or FILES_DIR / bin_name)
        return

    db = nfsbin.parse(source)
    print()
    tui.kv([
        ("Berkas", source),
        ("Entri", _num(db.count)),
    ])

    print()
    tui.section("2. String yang dihapus")
    key_text = tui.ask("Key (0x...)")
    key = nfstable.parse_key(key_text)
    if key is None:
        tui.err(
            "Key '%s' tidak dapat dibaca. Tulis heksadesimal, mis. "
            "0x1234ABCD." % key_text
        )
        return
    if not 0 < key <= 0xFFFFFFFF:
        tui.err("Key 0x%X di luar rentang u32." % key)
        return

    texts = db.text_by_key()
    payload = texts.get(key)
    if payload is None:
        tui.err("Key 0x%08X tidak ada di %s." % (key, source.name))
        tui.note("Lihat kolom Key pada tabel hasil Export.")
        return

    labels_path = _auto_labels()
    label = ""
    if labels_path is not None and labels_path.resolve() != Path(source).resolve():
        try:
            label_map = nfsbin.parse(labels_path).text_by_key()
        except (ValueError, OSError):
            label_map = {}
        if key in label_map:
            label = label_map[key].decode(nfsbin.ENCODING)
    else:
        labels_path = None

    print()
    tui.kv([
        ("Key", "0x%08X" % key),
        ("Label", label or "(kosong)"),
        ("Teks", nfstxt.escape_text(payload.decode(nfsbin.ENCODING))),
    ])

    print()
    default_out = Path(source).stem + "_new.bin"
    out = tui.ask("Nama berkas hasil", default_out)

    target_labels: Path | None = None
    if labels_path is not None and label:
        print()
        if tui.confirm(
            "Hapus juga labelnya dari salinan %s" % DEFAULT_LABELS, False
        ):
            target_labels = labels_path

    print()
    if not tui.confirm("Lanjutkan", True):
        tui.abort("Dibatalkan.")
        return

    print()
    tui.rule()
    code = run_remove_string(
        source, "0x%08X" % key, out, target_labels, None
    )
    if code == 0:
        print()
        tui.ok("Selesai.")


def _menu_info() -> None:
    tui.screen("Info  (struktur .bin)")
    bins = _bins_in_files()
    if not bins:
        tui.err("Tidak ada berkas .bin di folder files.")
        return
    tui.section("Pilih berkas")
    name = tui.pick(_names(bins), "Berkas .bin", _default_bin_name())
    print()
    run_info(name)


def _menu_verify() -> None:
    tui.screen("Verify  (uji round-trip)")
    bins = _bins_in_files()
    tui.section("Pilih berkas")
    if bins:
        print("    %s semua berkas .bin (%d)" % (tui.style("0.", "cyan"), len(bins)))
        name = tui.pick(_names(bins), "Berkas .bin (0 = semua)",
                        _default_bin_name(), allow_zero=True)
    else:
        name = tui.ask("Berkas/pola .bin", "*.bin")

    print()
    if name == "0":
        run_verify(["*.bin"])
    else:
        run_verify([name])


def _menu_open_files() -> None:
    import subprocess

    _ensure_files_dir()
    print()
    tui.note("Membuka %s" % FILES_DIR)
    try:
        if sys.platform == "win32":
            import os

            os.startfile(str(FILES_DIR))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(FILES_DIR)], check=False)
        else:
            subprocess.run(["xdg-open", str(FILES_DIR)], check=False)
    except OSError as exc:
        tui.err("Tidak bisa membuka folder: %s" % exc)
        tui.note("Buka manual: %s" % FILES_DIR)


# ---------------------------------------------------------------- argumen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Ekspor dan impor basis data string NFSMW (.bin <-> xlsx/csv), "
                    "termasuk jembatan txt serta tambah dan hapus string. "
                    "Berkas kerja dibaca dan ditulis di folder 'files'.",
        epilog="Jalankan tanpa argumen untuk masuk menu interaktif.",
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("export", help="ekspor .bin ke xlsx/csv")
    p.add_argument("--bin", help="berkas .bin sumber (baku: files/English.bin)")
    p.add_argument("--labels", help="Labels.bin untuk kolom Label "
                                    "(baku: files/Labels.bin bila ada)")
    p.add_argument("-o", "--output", help="berkas atau folder hasil "
                                          "(baku: files/<nama>.xlsx)")
    p.add_argument("--format", choices=["xlsx", "csv"], default="xlsx")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("import", help="impor xlsx/csv menjadi .bin")
    p.add_argument("table", help="berkas .xlsx atau .csv (dicari di files/)")
    p.add_argument("--bin", help="berkas .bin sumber (baku: files/English.bin)")
    p.add_argument("-o", "--output", help="berkas .bin hasil "
                                          "(baku: files/<tabel>_new.bin)")
    p.add_argument("--force", action="store_true",
                   help="tetap tulis hasil walau ada error validasi")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("check", help="periksa tabel tanpa menulis")
    p.add_argument("table")
    p.add_argument("--bin", help="berkas .bin sumber (baku: files/English.bin)")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("to-txt", help="ambil kolom Index dan Text menjadi .txt")
    p.add_argument("table", help="berkas .xlsx atau .csv (dicari di files/)")
    p.add_argument("-o", "--output", help="berkas .txt hasil "
                                          "(baku: files/<tabel>.txt)")
    p.set_defaults(func=cmd_to_txt)

    p = sub.add_parser("from-txt", help="tulis tabel baru dari .txt dan tabel dasar")
    p.add_argument("txt", help="berkas .txt berformat 'index, text' "
                               "(dicari di files/)")
    p.add_argument("--base", required=True,
                   help="tabel dasar .xlsx/.csv untuk Index, Key, dan Label")
    p.add_argument("-o", "--output", help="berkas tabel hasil "
                                          "(baku: files/<txt>_new.<format dasar>)")
    p.set_defaults(func=cmd_from_txt)

    p = sub.add_parser("add-string", help="tambah satu string baru ke .bin")
    p.add_argument("--bin", help="berkas .bin sumber (baku: files/English.bin)")
    p.add_argument("--key", help="key heksadesimal, mis. 0x1234ABCD; "
                                 "kosong/auto = hash dari --label")
    p.add_argument("--label", default="",
                   help="label untuk kolom Label (tidak disimpan di berkas bahasa)")
    p.add_argument("--text", required=True, help="teks string baru")
    p.add_argument("--escape", action="store_true",
                   help="tafsirkan \\xHH pada --text sebagai byte kontrol")
    p.add_argument("--labels", help="Labels.bin yang ikut ditambah labelnya")
    p.add_argument("--labels-out", help="hasil Labels.bin "
                                        "(baku: files/<nama>_new.bin)")
    p.add_argument("-o", "--output", help="berkas .bin hasil "
                                          "(baku: files/<nama>_new.bin)")
    p.set_defaults(func=cmd_add_string)

    p = sub.add_parser("remove-string", help="hapus string dari .bin menurut key")
    p.add_argument("--bin", help="berkas .bin sumber (baku: files/English.bin)")
    p.add_argument("--key", dest="keys", action="append", required=True,
                   metavar="KEY", help="key yang dihapus, mis. 0x1234ABCD "
                                       "(boleh diulang)")
    p.add_argument("--labels", help="Labels.bin yang ikut dihapus labelnya")
    p.add_argument("--labels-out", help="hasil Labels.bin "
                                        "(baku: files/<nama>_new.bin)")
    p.add_argument("-o", "--output", help="berkas .bin hasil "
                                          "(baku: files/<nama>_new.bin)")
    p.set_defaults(func=cmd_remove_string)

    p = sub.add_parser("info", help="tampilkan struktur .bin")
    p.add_argument("bin", nargs="?", help="berkas .bin (baku: files/English.bin)")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("verify", help="uji round-trip .bin")
    p.add_argument("bins", nargs="+", help="berkas atau pola glob, mis. \"*.bin\"")
    p.set_defaults(func=cmd_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tui.enable()
    _ensure_files_dir()

    if not argv:
        return menu()

    args = build_parser().parse_args(argv)
    if not getattr(args, "func", None):
        return menu()

    try:
        return args.func(args)
    except FileNotFoundError as exc:
        tui.err("Berkas tidak ditemukan: %s" % exc)
        return 2
    except ValueError as exc:
        tui.err("Format tidak dikenali: %s" % exc)
        return 2
    except RuntimeError as exc:
        tui.err(str(exc))
        return 2


def entry(argv: list[str] | None = None) -> int:
    """Titik masuk yang aman terhadap Ctrl+C.

    Ctrl+C di mana pun -- saat mengisi menu, saat menulis berkas, saat
    membaca tabel -- berakhir sebagai pesan singkat dan kode keluar 130,
    bukan traceback.
    """
    try:
        return main(argv)
    except (KeyboardInterrupt, tui.Cancelled):
        tui.abort("Dibatalkan.")
        return 130
    except BrokenPipeError:  # pragma: no cover
        return 0
    except Exception as exc:  # noqa: BLE001
        tui.err("%s: %s" % (type(exc).__name__, exc))
        tui.note("Jalankan ulang dengan --debug untuk detail.")
        if "--debug" in (sys.argv if argv is None else argv):
            raise
        return 1


if __name__ == "__main__":
    try:
        code = entry()
    except KeyboardInterrupt:  # pragma: no cover
        code = 130
    try:
        sys.exit(code)
    except SystemExit:
        raise