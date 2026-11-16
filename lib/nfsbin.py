"""nfsbin -- pustaka baca/tulis database string Need for Speed Most Wanted.

Format yang ditangani
---------------------
Berkas bahasa NFSMW (``English.bin``, ``German.bin``, ``Labels.bin``, dst.)
adalah basis data pasangan ``key -> teks``. Struktur berikut sudah
diverifikasi lewat uji round-trip byte-identik pada 14 berkas bahasa
sekaligus, termasuk satu berkas original tanpa penanda repack.

Tata letak
----------
::

    offset  isi
    ------  ------------------------------------------------------------
    0x0000  u32 x6  header
                      [0] ID blok STRBlocks (0x39000)
                      [1] penunjuk akhir blob string (+delta, lihat catatan)
                      [2] konstanta 0x20
                      [3] COUNT (jumlah entri)
                      [4] penunjuk blok tabel (menunjuk ke sentinel)
                      [5] alamat entri terakhir = table_start + 8*(COUNT-1)
    0x0018  ...     blok "GLOBAL" (opaque, disalin apa adanya)
    0x1824  u64     sentinel {0, 0} -- bukan entri
    0x182C  ...     tabel entri: COUNT x {u32 key, u32 offset}
    base    ...     blob string, setiap string diakhiri byte NUL
    tail    ...     blok resource font (FNTF/gMpB/padding) -- opaque

Relasi yang berlaku pada seluruh berkas bahasa::

    table_start = hdr[4] + 8
    base        = table_start + 8 * COUNT
    alamat teks = base + entry.offset

Catatan penting
---------------
- ``hdr[1]`` tidak dapat dihitung ulang secara absolut. Selisihnya terhadap
  akhir blob string bervariasi antar berkas (-8 sampai +7), jadi nilai delta
  aslinya disimpan lalu digeser bersama blob saat menulis ulang.
- ``hdr[0]`` berisi 0x39000 di seluruh berkas yang diperiksa, yaitu ID blok
  ``STRBlocks``. Nilainya tidak diubah saat menulis ulang.
- Blob string disimpan sekali per offset unik. Dua key boleh menunjuk offset
  yang sama (alias), tetapi byte string-nya hanya satu.
- Urutan tabel tidak boleh berubah karena game melakukan pencarian pada kolom
  key yang terurut naik.
- Encoding teks adalah byte tunggal (latin-1), bukan UTF-8.
- Menambah entri (:func:`insert_entries`) menggeser awal blob 8 byte, lalu
  menaruh teks baru di akhir blob. Tabel diurutkan ulang menurut key; seluruh
  key dan teks lama tidak berubah.
- Menghapus entri (:func:`remove_entries`) menyusutkan tabel 8 byte per entri,
  sehingga awal blob dan offset entri tersisa digeser. Teks yang tidak lagi
  dipakai ikut dibuang dari blob.

Contoh
------
>>> import nfsbin
>>> db = nfsbin.parse("English.bin")
>>> db.count
5811
>>> db.text_by_key()[0x00000474]
b'@'
>>> nfsbin.rebuild(db) == db.raw
True
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "StringDB",
    "parse",
    "rebuild",
    "insert_entries",
    "remove_entries",
    "replace_text",
    "binhash",
    "verify_roundtrip",
    "inspect_header",
    "check_text",
    "MAX_COUNT",
    "ENCODING",
]

HEADER_SIZE = 24
SENTINEL_SIZE = 8
EXPECTED_CONST = 0x20

#: Batas aman jumlah entri saat memuat berkas asing.
MAX_COUNT = 2_000_000

#: Encoding byte tunggal yang dipakai seluruh berkas bahasa NFSMW.
ENCODING = "latin-1"


@dataclass
class StringDB:
    """Satu berkas basis data string."""

    path: Path
    raw: bytes
    hdr: tuple[int, int, int, int, int, int]
    table_start: int
    base: int
    entries: list[tuple[int, int]] = field(default_factory=list)
    texts: list[bytes] = field(default_factory=list)
    tail: bytes = b""
    blob_end: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        """Jumlah entri."""
        return len(self.entries)

    @property
    def keys(self) -> list[int]:
        """Daftar key sesuai urutan berkas."""
        return [key for key, _ in self.entries]

    @property
    def sha256(self) -> str:
        """Sidik jari SHA-256 berkas asal."""
        return hashlib.sha256(self.raw).hexdigest().upper()

    @property
    def hdr1_delta(self) -> int:
        """Selisih hdr[1] terhadap akhir blob string (dipertahankan saat tulis)."""
        return self.hdr[1] - self.blob_end

    def text_by_key(self) -> dict[int, bytes]:
        """Pemetaan ``key -> teks``."""
        return {key: text for (key, _), text in zip(self.entries, self.texts)}

    def problems(self) -> list[str]:
        """Periksa konsistensi internal. Kosong berarti sehat."""
        result: list[str] = []

        keys = self.keys
        if keys != sorted(keys):
            result.append("kolom key tidak terurut naik")
        if len(set(keys)) != len(keys):
            result.append("terdapat key duplikat")

        if self.hdr[3] != self.count:
            result.append(
                "header count (%d) tidak sama dengan jumlah entri (%d)"
                % (self.hdr[3], self.count)
            )
        expected_last = self.table_start + 8 * (self.count - 1)
        if self.hdr[5] != expected_last:
            result.append(
                "header[5] = 0x%X, seharusnya 0x%X" % (self.hdr[5], expected_last)
            )
        if self.hdr[2] != EXPECTED_CONST:
            result.append(
                "header[2] = 0x%X, biasanya 0x%X" % (self.hdr[2], EXPECTED_CONST)
            )

        lengths: dict[int, int] = {}
        for (_, off), text in zip(self.entries, self.texts):
            lengths[off] = max(lengths.get(off, 0), len(text))
        cursor = 0
        for off in sorted(lengths):
            if off < cursor:
                result.append("offset 0x%X tumpang tindih" % off)
                break
            cursor = off + lengths[off] + 1

        if not self.tail:
            result.append("tidak ada data sesudah blob string")
        return result


def inspect_header(raw: bytes) -> dict[str, int | bool]:
    """Tafsirkan header tanpa memuat seluruh entri."""
    if len(raw) < HEADER_SIZE:
        raise ValueError("berkas terlalu pendek untuk header (%d byte)" % len(raw))
    hdr = struct.unpack_from("<6I", raw, 0)
    table_start = hdr[4] + SENTINEL_SIZE
    return {
        "hdr0": hdr[0],
        "hdr1": hdr[1],
        "konstanta": hdr[2],
        "count": hdr[3],
        "table_ptr": hdr[4],
        "last_entry": hdr[5],
        "table_start": table_start,
        "base": table_start + 8 * hdr[3],
        "sentinel_kosong": raw[hdr[4]:hdr[4] + SENTINEL_SIZE] == b"\x00" * SENTINEL_SIZE,
    }


def parse(path: str | Path) -> StringDB:
    """Urai berkas ``.bin`` menjadi :class:`StringDB`."""
    path = Path(path)
    raw = path.read_bytes()
    total = len(raw)
    if total < HEADER_SIZE + SENTINEL_SIZE:
        raise ValueError("%s: berkas terlalu kecil (%d byte)" % (path.name, total))

    hdr = struct.unpack_from("<6I", raw, 0)
    count = hdr[3]
    if count <= 0 or count > MAX_COUNT:
        raise ValueError("%s: jumlah entri tidak masuk akal (%d)" % (path.name, count))

    table_start = hdr[4] + SENTINEL_SIZE
    base = table_start + 8 * count
    if table_start < HEADER_SIZE or base > total:
        raise ValueError(
            "%s: tata letak di luar berkas (table=0x%X base=0x%X size=%d)"
            % (path.name, table_start, base, total)
        )

    entries: list[tuple[int, int]] = []
    texts: list[bytes] = []
    for index in range(count):
        key, off = struct.unpack_from("<II", raw, table_start + 8 * index)
        position = base + off
        if position >= total:
            raise ValueError(
                "%s: entri %d menunjuk 0x%X, di luar berkas"
                % (path.name, index, position)
            )
        terminator = raw.find(b"\x00", position)
        if terminator < 0:
            raise ValueError(
                "%s: entri %d tidak diakhiri byte NUL" % (path.name, index)
            )
        entries.append((key, off))
        texts.append(raw[position:terminator])

    blob_end = 0
    for (_, off), text in zip(entries, texts):
        blob_end = max(blob_end, base + off + len(text) + 1)

    db = StringDB(
        path=path,
        raw=raw,
        hdr=hdr,
        table_start=table_start,
        base=base,
        entries=entries,
        texts=texts,
        tail=raw[blob_end:],
        blob_end=blob_end,
    )

    if not inspect_header(raw)["sentinel_kosong"]:
        db.warnings.append("sentinel di hdr[4] tidak nol semua")
    if blob_end > total:
        db.warnings.append("blob string melewati akhir berkas")
    return db


def check_text(payload: bytes, index: int = -1) -> None:
    """Pastikan teks dapat ditulis apa adanya ke berkas.

    Melempar :class:`ValueError` bila teks mengandung NUL atau tidak dapat
    diwakili encoding :data:`ENCODING`.
    """
    if b"\x00" in payload:
        raise ValueError("teks indeks %d mengandung byte NUL" % index)
    try:
        payload.decode(ENCODING)
    except UnicodeDecodeError as exc:
        raise ValueError(
            "teks indeks %d tidak dapat diwakili encoding %s: %s"
            % (index, ENCODING, exc)
        ) from exc


def binhash(value: str) -> int:
    """Hitung *binary hash* NFS dari sebuah label.

    Algoritma ini mulai dari ``0xFFFFFFFF``, lalu untuk tiap karakter
    ``hasil = hasil * 0x21 + byte``. Label yang berbentuk ``0x1234ABCD``
    dibaca sebagai nilai heksadesimal.
    """
    text = value
    if not text or text.isspace() or text.upper() == "NULL":
        return 0
    if text[:2].lower() == "0x" and len(text) <= 10:
        digits = text[2:]
        if digits and all(c in "0123456789abcdefABCDEF" for c in digits):
            return int(digits, 16) & 0xFFFFFFFF

    result = 0xFFFFFFFF
    for char in text:
        result = (result * 0x21 + (ord(char) & 0xFF)) & 0xFFFFFFFF
    return result


def _assemble(
    db: StringDB,
    entries: list[tuple[int, int]],
    texts: list[bytes],
) -> bytes:
    """Susun berkas dari daftar entri dan teks yang sejajar."""
    if not entries:
        raise ValueError("tidak boleh menyisakan nol entri")
    if len(texts) != len(entries):
        raise ValueError(
            "jumlah teks (%d) tidak sama dengan jumlah entri (%d)"
            % (len(texts), len(entries))
        )

    # Satu wakil per offset unik: key pertama yang menunjuk offset tersebut.
    representative: dict[int, int] = {}
    for index, (_, off) in enumerate(entries):
        representative.setdefault(off, index)

    new_offset: dict[int, int] = {}
    blob = bytearray()
    for old_off in sorted(representative):
        index = representative[old_off]
        payload = texts[index]
        check_text(payload, index)
        new_offset[old_off] = len(blob)
        blob += payload + b"\x00"

    out = bytearray()
    out += db.raw[: db.table_start]
    for key, off in entries:
        out += struct.pack("<II", key, new_offset[off])
    out += blob
    out += db.tail

    base = db.table_start + 8 * len(entries)
    # hdr[1] bukan alamat absolut: delta aslinya dipertahankan.
    struct.pack_into("<I", out, 0x04, base + len(blob) + db.hdr1_delta)
    struct.pack_into("<I", out, 0x0C, len(entries))
    struct.pack_into("<I", out, 0x14, base - 8)
    return bytes(out)


def rebuild(db: StringDB, texts: list[bytes] | None = None) -> bytes:
    """Bangun ulang isi berkas dari entri dan teks.

    Offset dihitung ulang, sehingga panjang tiap teks boleh berubah. Urutan
    tabel dan seluruh nilai ``key`` dipertahankan.
    """
    source = db.texts if texts is None else list(texts)
    return _assemble(db, db.entries, source)


def insert_entries(
    db: StringDB, additions: list[tuple[int, bytes]]
) -> bytes:
    """Tambah entri baru ke salinan berkas, lalu urutkan tabel menurut ``Key``.

    ``additions`` berisi pasangan ``(key, teks)``. Semua key harus unik, tidak
    nol, dan belum ada di berkas. Entri lama tidak diubah; hanya posisinya di
    tabel yang bergeser bila key baru berada di tengah. Teks baru diletakkan
    di akhir blob lama.

    Struktur yang diperbarui: jumlah entri (``hdr[3]``), alamat entri terakhir
    (``hdr[5]``), penunjuk akhir blob (``hdr[1]``), serta offset tiap entri.
    """
    keys = db.keys
    if keys != sorted(keys):
        raise ValueError("%s: kolom key tidak terurut naik" % db.path.name)
    if len(set(keys)) != len(keys):
        raise ValueError("%s: terdapat key duplikat" % db.path.name)
    if not additions:
        return rebuild(db)

    pairs: list[tuple[tuple[int, int], bytes]] = list(
        zip(db.entries, db.texts)
    )
    seen = set(keys)
    next_offset = max((off for _, off in db.entries), default=-1) + 1

    for key, payload in additions:
        if not isinstance(key, int) or isinstance(key, bool):
            raise ValueError("key harus berupa angka: %r" % (key,))
        if not 0 < key <= 0xFFFFFFFF:
            raise ValueError("key 0x%X di luar rentang u32" % key)
        if key in seen:
            raise ValueError("key 0x%08X sudah ada di %s" % (key, db.path.name))
        if not isinstance(payload, (bytes, bytearray)):
            raise ValueError("teks key 0x%08X harus berupa bytes" % key)
        payload = bytes(payload)
        check_text(payload, key)
        seen.add(key)
        pairs.append(((key, next_offset), payload))
        next_offset += 1

    pairs.sort(key=lambda pair: pair[0][0])
    return _assemble(
        db,
        [entry for entry, _ in pairs],
        [text for _, text in pairs],
    )


def remove_entries(db: StringDB, keys: list[int]) -> bytes:
    """Hapus entri dari salinan berkas tanpa mengubah entri yang tersisa.

    ``keys`` berisi key yang akan dihapus. Semua key harus ada, berupa angka
    ``u32``, dan tidak boleh duplikat. Tabel menyusut 8 byte per entri,
    sehingga awal blob dan seluruh offset digeser; teks milik entri yang
    tersisa tidak berubah. Bila dua key memakai offset yang sama, teks itu
    tetap disimpan selama salah satunya masih ada.
    """
    if not keys:
        raise ValueError("tidak ada key yang akan dihapus")

    seen: set[int] = set()
    for key in keys:
        if not isinstance(key, int) or isinstance(key, bool):
            raise ValueError("key harus berupa angka: %r" % (key,))
        if not 0 < key <= 0xFFFFFFFF:
            raise ValueError("key 0x%X di luar rentang u32" % key)
        if key in seen:
            raise ValueError("key 0x%08X muncul lebih dari sekali" % key)
        seen.add(key)

    existing = set(db.keys)
    missing = [key for key in keys if key not in existing]
    if missing:
        raise ValueError(
            "key %s tidak ada di %s"
            % (", ".join("0x%08X" % key for key in missing[:5]), db.path.name)
        )

    pairs = [
        (entry, text)
        for entry, text in zip(db.entries, db.texts)
        if entry[0] not in seen
    ]
    if not pairs:
        raise ValueError("tidak boleh menghapus seluruh entri berkas")

    return _assemble(
        db,
        [entry for entry, _ in pairs],
        [text for _, text in pairs],
    )


def replace_text(db: StringDB, key: int, payload: bytes) -> bytes:
    """Ganti teks satu key tanpa menyentuh key lain.

    Bila ``key`` berbagi offset dengan key lain, entri itu dipindahkan ke
    offset baru supaya teks pasangannya tidak ikut berubah. Urutan tabel dan
    seluruh nilai key dipertahankan.
    """
    if not isinstance(key, int) or isinstance(key, bool):
        raise ValueError("key harus berupa angka: %r" % (key,))
    if not 0 < key <= 0xFFFFFFFF:
        raise ValueError("key 0x%X di luar rentang u32" % key)
    if not isinstance(payload, (bytes, bytearray)):
        raise ValueError("teks key 0x%08X harus berupa bytes" % key)
    payload = bytes(payload)
    check_text(payload, key)

    index = None
    for position, (existing, _) in enumerate(db.entries):
        if existing == key:
            index = position
            break
    if index is None:
        raise ValueError("key 0x%08X tidak ada di %s" % (key, db.path.name))

    old_offset = db.entries[index][1]
    shared = sum(1 for _, off in db.entries if off == old_offset) > 1

    entries = list(db.entries)
    texts = list(db.texts)
    if shared:
        entries[index] = (key, max((off for _, off in db.entries), default=-1) + 1)
    texts[index] = payload
    return _assemble(db, entries, texts)


def verify_roundtrip(path: str | Path) -> tuple[bool, str]:
    """Uji ``parse -> rebuild`` tanpa modifikasi; harus byte-identik."""
    db = parse(path)
    produced = rebuild(db)
    if produced == db.raw:
        return True, "identik (%d byte)" % len(produced)
    limit = min(len(produced), len(db.raw))
    for i in range(limit):
        if produced[i] != db.raw[i]:
            return False, "beda pertama di 0x%X (asli %02X, hasil %02X)" % (
                i,
                db.raw[i],
                produced[i],
            )
    return False, "panjang berbeda: asli %d, hasil %d" % (len(db.raw), len(produced))