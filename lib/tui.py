"""tui -- tampilan dan interaksi terminal untuk NFSMW Lang Tool.

Seluruh keluaran layar dan pembacaan masukan lewat modul ini supaya tampilan
konsisten dan Ctrl+C selalu berakhir rapi tanpa traceback.

Prinsip
-------
- **ASCII saja.** Tidak ada karakter kotak, centang, atau emoji. Konsol
  Windows dengan code page lama akan gagal mencetaknya dan melempar
  ``UnicodeEncodeError`` di tengah menu.
- **Warna ANSI, dinyalakan kondisional.** Hanya bila stdout benar-benar
  terminal dan console mendukung VT. Set ``NO_COLOR`` untuk mematikan.
- **Aman untuk pipe.** Bila masukan dialihkan, layar tidak dibersihkan dan
  tidak ada kode ANSI, sehingga berkas log tetap terbaca.
- **Tidak pernah mengulang tanpa akhir.** Akhir masukan (EOF) diperlakukan
  sebagai pembatalan, bukan loop.
"""

from __future__ import annotations

import os
import shutil
import sys
import textwrap

__all__ = [
    "Cancelled",
    "enable",
    "clear",
    "width",
    "banner",
    "bullets",
    "screen",
    "section",
    "rule",
    "kv",
    "menu",
    "pick",
    "ask",
    "confirm",
    "pause",
    "ok",
    "warn",
    "err",
    "note",
    "abort",
    "style",
    "redirected",
    "reset_lines",
]


class Cancelled(Exception):
    """Masukan berakhir (EOF) atau pengguna membatalkan."""


# ---------------------------------------------------------------- warna

_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "gray": "\033[90m",
    "white": "\033[97m",
}

_ENABLED = False
_TTY = False


def _enable_vt() -> bool:
    """Nyalakan pemrosesan escape ANSI di console Windows."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:  # noqa: BLE001
        return False


def enable(force: bool | None = None) -> None:
    """Siapkan modul. Panggil sekali di awal ``main()``."""
    global _ENABLED, _TTY
    _TTY = sys.stdin.isatty() and sys.stdout.isatty()
    if force is not None:
        _ENABLED = force
        return
    if os.environ.get("NO_COLOR"):
        _ENABLED = False
        return
    _ENABLED = _TTY and _enable_vt()


def style(text: str, *names: str) -> str:
    """Beri warna. Tanpa warna, teks dikembalikan apa adanya."""
    if not _ENABLED or not names:
        return text
    prefix = "".join(_CODES.get(n, "") for n in names)
    return prefix + text + _CODES["reset"]


def redirected() -> bool:
    """True bila masukan atau keluaran dialihkan (pipe, berkas log).

    Saat dialihkan, layar tidak dibersihkan dan tidak ada jeda Enter agar
    alur tetap bisa dijalankan dari skrip dan lognya tetap terbaca.
    """
    return not _TTY


def width(default: int = 80) -> int:
    """Lebar terminal, dibatasi agar tetap enak dibaca."""
    try:
        columns = shutil.get_terminal_size((default, 24)).columns
    except OSError:  # pragma: no cover
        columns = default
    return max(40, min(columns, 100))


# ---------------------------------------------------------------- layar


def clear() -> None:
    """Bersihkan layar (termasuk riwayat gulir bila didukung). No-op bila dipipe."""
    try:
        interactive = sys.stdout.isatty()
    except (AttributeError, ValueError):  # pragma: no cover
        interactive = False
    if not interactive:
        return

    # Kalau console lama tidak menerima escape ANSI, ``cls`` adalah satu-satunya
    # cara membersihkan layar. Tanpa ini layar menu baru menumpuk di bawah teks
    # lama.
    if os.name == "nt" and not _ENABLED:
        try:
            sys.stdout.flush()
            os.system("cls")
            return
        except OSError:  # pragma: no cover
            pass

    sys.stdout.write("\033[H\033[2J\033[3J")
    sys.stdout.flush()


def reset_lines(count: int = 1) -> None:
    """Hapus ``count`` baris terakhir (untuk masukan yang salah)."""
    if not _TTY or count <= 0:
        return
    sys.stdout.write("\033[1A\033[2K" * count)
    sys.stdout.flush()


def rule(char: str = "-") -> None:
    print("  " + style(char * min(width() - 3, 68), "gray"))


_ART = [
    r" _   _ _____ ____  __  __ __        __",
    r"| \ | |  ___/ ___||  \/  |\ \      / /",
    r"|  \| | |_  \___ \| |\/| | \ \ /\ / / ",
    r"| |\  |  _|  ___) | |  | |  \ V  V /  ",
    r"|_| \_|_|   |____/|_|  |_|   \_/\_/   ",
]


def banner(version: str, author: str, folder: str | None = None) -> None:
    """Cetak nama tool dan folder kerja. Layar dibersihkan oleh pemanggil."""
    print()
    for line in _ART:
        print("  " + style(line, "cyan", "bold"))
    print()
    pairs = [
        ("Author", author),
        ("Version", version),
    ]
    if folder:
        pairs.append(("Folder", folder))
    kv(pairs)
    print()


def bullets(items, indent: int = 3) -> None:
    """Daftar butir dengan awalan strip, dibungkus rata dengan teksnya."""
    pad = " " * indent
    for item in items:
        if isinstance(item, tuple):
            head, detail = item
            text = head + " : " + detail
        else:
            text = str(item)
        prefix_len = indent + 2
        wrapped = textwrap.wrap(text, width=max(20, width() - prefix_len)) or [""]
        first = wrapped[0]
        if isinstance(item, tuple):
            head, detail = item
            if first.startswith(head + " : "):
                first = style(head, "white") + " : " + first[len(head) + 3:]
        print(pad + style("- ", "gray") + first)
        for extra in wrapped[1:]:
            print(" " * prefix_len + extra)


def screen(title: str, app: str = "NFSMW Lang Tool") -> None:
    """Bersihkan layar lalu tampilkan judul layar."""
    clear()
    print()
    print("  " + style(app, "gray"))
    print("  " + style(title, "bold", "white"))
    print("  " + style("-" * min(width() - 5, 64), "gray"))
    print()


def section(title: str) -> None:
    """Judul bagian di tengah layar."""
    print("  " + style("[" + title + "]", "bold", "white"))


def kv(pairs, indent: int = 2, sep: str = " : ") -> None:
    """Cetak pasangan label/nilai sejajar, membungkus nilai yang panjang."""
    rows = [(str(k), "" if v is None else str(v)) for k, v in pairs]
    if not rows:
        return
    label_w = max(len(k) for k, _ in rows)
    pad = " " * indent
    prefix_len = indent + label_w + len(sep)

    for label, value in rows:
        head = pad + style(label.ljust(label_w), "gray") + style(sep, "gray")
        if not value:
            print(head.rstrip())
            continue
        wrapped = textwrap.wrap(
            value, width=max(20, width() - prefix_len - 2)
        ) or [""]
        print(head + wrapped[0])
        for extra in wrapped[1:]:
            print(" " * prefix_len + extra)


# ---------------------------------------------------------------- masukan


def _prompt_text(label: str, hint: str | None = None) -> str:
    body = label + (" [%s]" % hint if hint else "")
    return "  " + style("[= ", "green") + body + style(" => ", "green")


def _read_raw(text: str) -> str:
    try:
        return input(text)
    except EOFError as exc:
        raise Cancelled() from exc


def _read_number(label: str, low: int, high: int) -> int:
    """Baca angka dalam rentang. Masukan salah dihapus, bukan dibiarkan."""
    while True:
        raw = _read_raw(_prompt_text(label)).strip()
        if low == 0 and raw.lower() in ("q", "quit", "exit", "keluar"):
            return 0
        try:
            value = int(raw)
        except ValueError:
            reset_lines(1)
            continue
        if low <= value <= high:
            return value
        reset_lines(1)


def menu(items, title: str = "Menu Utama", label: str = "Pilih") -> int:
    """Tampilkan menu bernomor. Kembalikan nomor pilihan, atau 0 untuk keluar."""
    section(title)
    entries = [entry if isinstance(entry, tuple) else (entry, "") for entry in items]
    number_w = len(str(len(entries)))
    text_w = max(len(text) for text, _ in entries)
    for index, (text, description) in enumerate(entries, 1):
        marker = style(("%*d." % (number_w, index)), "cyan")
        line = "    %s %s" % (marker, text.ljust(text_w))
        if description:
            line += "   " + style(description, "gray")
        print(line.rstrip())
    print()
    return _read_number(label, 0, len(entries))


def pick(names, label: str, default: str | None = None, allow_zero: bool = False) -> str:
    """Pilih berkas dari daftar: boleh nomor, nama, atau path lain.

    ``allow_zero`` menerima ``0`` sebagai nilai khusus (mis. "semua berkas")
    dan mengembalikannya sebagai teks ``"0"``.
    """
    for index, name in enumerate(names, 1):
        print("    %s %s" % (style("%d." % index, "cyan"), name))
    print()
    while True:
        raw = _read_raw(_prompt_text(label, default)).strip().strip('"')
        if not raw:
            if default:
                return default
            reset_lines(1)
            continue
        if allow_zero and raw == "0":
            return "0"
        if raw.isdigit():
            number = int(raw)
            if 1 <= number <= len(names):
                return names[number - 1]
            reset_lines(1)
            continue
        return raw


def ask(label: str, default: str | None = None) -> str:
    """Baca satu baris teks. Kosong berarti memakai nilai baku."""
    while True:
        raw = _read_raw(_prompt_text(label, default)).strip().strip('"')
        if raw:
            return raw
        if default is not None:
            return default
        reset_lines(1)


def ask_optional(label: str, default: str | None = None) -> str:
    """Baca satu baris teks yang boleh kosong.

    Berbeda dari :func:`ask`, kosong tanpa nilai baku tetap diterima dan
    dikembalikan sebagai string kosong.
    """
    raw = _read_raw(_prompt_text(label, default)).strip().strip('"')
    if not raw and default is not None:
        return default
    return raw


def ask_text(label: str, default: str | None = None) -> str:
    """Baca satu baris teks apa adanya, termasuk spasi di awal dan akhir."""
    raw = _read_raw(_prompt_text(label, default))
    if not raw and default is not None:
        return default
    return raw


def confirm(label: str, default: bool = True) -> bool:
    """Tanya ya/tidak. Masukan salah diulang tanpa meninggalkan jejak."""
    hint = "Y/n" if default else "y/N"
    while True:
        raw = _read_raw(_prompt_text(label, hint)).strip().lower()
        if not raw:
            return default
        if raw in ("y", "ya", "yes"):
            return True
        if raw in ("t", "tidak", "n", "no"):
            return False
        reset_lines(1)


def pause(label: str = "Tekan Enter") -> None:
    """Berhenti sebentar agar hasil terbaca. Tidak memblokir saat dipipe.

    Setelah Enter, layar dibersihkan supaya menu berikutnya tidak menumpuk
    di bawah hasil aksi sebelumnya.
    """
    if not _TTY:
        return
    print()
    try:
        input(style("  [%s] " % label, "gray"))
    except EOFError:
        pass
    clear()


# ---------------------------------------------------------------- pesan


def ok(message: str) -> None:
    print(style("  [OK] ", "green", "bold") + message)


def warn(message: str) -> None:
    print(style("  [!]  ", "yellow", "bold") + message)


def err(message: str) -> None:
    print(style("  [x]  ", "red", "bold") + message)


def note(message: str) -> None:
    print(style("  ...  ", "gray") + message)


def abort(message: str = "Dibatalkan.") -> None:
    """Penutup saat Ctrl+C atau masukan berakhir."""
    if _TTY:
        sys.stdout.write("\n")
    print(style("  " + message, "gray"))