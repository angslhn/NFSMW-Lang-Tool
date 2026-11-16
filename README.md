# NFSMW Lang Tool

Alat pengelola basis data string **Need for Speed Most Wanted** (2005, Black
Edition). Enam jalur, semuanya bekerja pada data:

- **Export** — `English.bin` → `English.xlsx` / `English.csv`
- **Import** — `English.xlsx` / `English.csv` → `English.bin`
- **TXT** — tabel ⇄ `English.txt` berformat `index, text`, hanya dua kolom
- **Tambah String** — menambahkan satu entri baru (`Key` + `Label` + `Text`)
- **Hapus String** — menghapus satu atau beberapa entri berdasarkan `Key`
- **Edit String** — mengubah `Text` dan/atau `Label` satu `Key` yang sudah ada

Semua entri masuk ke tabel empat kolom, diedit sepuasnya di Excel, lalu
dikembalikan menjadi berkas `.bin` yang sah. Tidak ada kategori, tidak ada
kolom tambahan.

Tambah dan Hapus String adalah operasi yang mengubah jumlah entri. Export,
Import, TXT, dan Edit String tidak pernah mengubah urutan tabel atau nilai
`Key` yang sudah ada.

---

## Taruh berkasnya di mana

Semua berkas kerja dibaca dan ditulis di **satu folder**, yaitu `files/` di
samping `main.py`. Tidak perlu mengatur path panjang.

```
NFSMW Lang Tool/
├── main.py
├── README.md
├── requirements.txt
└── files/
    ├── English.bin      # File bahasa
    ├── Labels.bin       # File pendamping
    ├── English.xlsx     # Hasil export
    ├── English.txt      # Teks saja: index, text
    ├── English_new.bin  # Hasil import / tambah / hapus string
    ├── English_edited.bin  # Hasil edit teks
    ├── Labels_new.bin   # Hasil tambah / hapus label
    └── Labels_edited.bin   # Hasil edit label
```

Folder `files/` dibuat otomatis kalau belum ada. Menu `10` membukanya di
Windows Explorer.

### `English.bin` butuh `Labels.bin`

Ini dua berkas yang berpasangan:

| Berkas        | Isi                              | Peran                    |
| ------------- | -------------------------------- | ------------------------ |
| `English.bin` | 5.811 entri: `key` → teks        | sumber teks, yang diedit |
| `Labels.bin`  | 4.627 entri: `key` → nama simbol | pengisi kolom `Label`    |

Keduanya tidak bisa digabung berdasarkan urutan baris, karena jumlah entrinya
beda (5.811 vs 4.627). Penggabungan dilakukan pada nilai `Key`, bukan posisi.

- **Dengan `Labels.bin`** — kolom `Label` terisi 4.626 dari 5.811 baris, jadi
  Anda tahu baris mana berisi teks menu (`AT`, `GPS`, `RAP_LOGIN2_...`) dan
  mana yang isi mod.
- **Tanpa `Labels.bin`** — tool tetap jalan normal, export tetap 5.811 baris,
  tetapi kolom `Label` kosong semua (`Berlabel : 0`). Import tetap bisa
  dilakukan dan hasilnya tetap sah.

`Labels.bin` diambil dari folder `LANGUAGES` game:

```
C:\Games\Need for Speed Most Wanted Black Edition\LANGUAGES\Labels.bin
```

Kalau `files/Labels.bin` ada, tool memakainya otomatis tanpa ditanya.

---

## Instalasi

Butuh Python 3.10 atau lebih baru.

```
pip install -r requirements.txt
```

Isi `requirements.txt` hanya `openpyxl` (untuk `.xlsx`). Untuk CSV saja
sebenarnya tidak wajib.

---

## Cara pakai

### Menu interaktif

```
python main.py
```

```
   _   _ _____ ____  __  __ __        __
  | \ | |  ___/ ___||  \/  |\ \      / /
  |  \| | |_  \___ \| |\/| | \ \ /\ / /
  | |\  |  _|  ___) | |  | |  \ V  V /
  |_| \_|_|   |____/|_|  |_|   \_/\_/

  Author  : Aang Solihin
  Version : 1.0
  Folder  : ...\NFSMW Lang Tool\files

  [Folder files]
    bin   English.bin           257,272 byte
    bin   Labels.bin            155,656 byte
    tabel English.xlsx          284,334 byte
    txt   English.txt           218,257 byte

  [Info]
   - Export : .bin menjadi tabel (.xlsx/.csv) berisi 4 kolom, siap diedit di
     Excel
   - Import : tabel yang sudah diedit dikembalikan menjadi .bin baru
   - Ke TXT : pilih tabel, lalu tulis teksnya saja ke .txt (tiap baris: index,
     text)
   - Dari TXT : pilih .txt dan tabel dasar, lalu tulis tabel baru dengan teks
     dari .txt
   - Tambah String : tambah satu key + label + text baru ke .bin
   - Hapus String : hapus satu atau beberapa key dari .bin
   - Edit String : ubah teks dan/atau label satu key di .bin
   - Info : lihat header dan tata letak satu berkas .bin
   - Verify : uji bahwa berkas .bin dibaca dan ditulis ulang persis sama

  Kolom tabel: Index, Key, Label, Text. Ubah hanya kolom Text.

  [Menu Utama]
    1. Export
    2. Import
    3. Ke TXT
    4. Dari TXT
    5. Tambah String
    6. Hapus String
    7. Edit String
    8. Info
    9. Verify
    10. Buka folder files
    11. Keluar

  [= Pilih =>
```

Layar utama menampilkan isi `files/`, keterangan singkat tiap menu, lalu
pilihan. Setiap pertanyaan punya nilai baku di dalam `[...]` — tekan Enter
untuk memakainya. Masukan yang salah (huruf, angka di luar rentang) dihapus
dan ditanya ulang, tidak membanjiri layar.

Daftar berkas bisa dipilih dengan **nomor** atau dengan mengetik namanya
langsung. Nama yang mengandung folder (`D:\kerja\English.bin`) dipakai apa
adanya.

Alur normal:

1. Taruh `English.bin` dan `Labels.bin` di `files/`.
2. Pilih **1** → hasil `files/English.xlsx`.
3. Buka `English.xlsx`, edit kolom `Text`.
4. Pilih **2** → hasil `files/English_new.bin`.
5. Salin `English_new.bin` ke `LANGUAGES\English.bin` (cadangkan dulu).

Alur teks saja, tanpa menyentuh empat kolom:

1. Pilih **1** dulu supaya ada `files/English.xlsx`.
2. Pilih **3 (Ke TXT)**, tentukan tabel dan nama `.txt` → `files/English.txt`.
3. Edit isi `English.txt` (hanya `index, text`).
4. Pilih **4 (Dari TXT)**, tentukan `.txt` dan tabel dasar → tabel baru.
5. Pilih **2 (Import)** untuk menjadikannya `.bin`.

Alur menambah string baru:

1. Pilih **5 (Tambah String)**.
2. Tentukan berkas `.bin` yang akan ditambah.
3. Isi `Label` (boleh kosong) dan `Key`. Kalau `Key` dikosongkan, tool
   menghitungnya dari `Label` dengan algoritma hash NFS.
4. Tulis `Text`. Gunakan `\xHH` untuk byte kontrol (`\x82` dan `\x83` untuk
   tanda kutip font game, misalnya).
5. Tentukan nama hasil. Bila `Labels.bin` ada dan `Label` diisi, tool juga
   menawarkan salinan `Labels_new.bin` yang sudah memuat label baru.
6. Salin `English_new.bin` dan (bila dipakai) `Labels_new.bin` ke folder
   `LANGUAGES` setelah mencadangkan berkas asli.

Alur menghapus string:

1. Pilih **6 (Hapus String)**.
2. Tentukan berkas `.bin` yang akan dihapus entrinya.
3. Tulis `Key` yang dihapus. Nilainya bisa dilihat di kolom `Key` pada tabel
   hasil Export.
4. Periksa ringkasan `Key`, `Label`, dan `Text` yang akan dihapus, lalu
   konfirmasi.
5. Tentukan nama hasil. Bila `Labels.bin` ada dan key itu punya label, tool
   menawarkan ikut menghapus labelnya dari salinan `Labels_new.bin`
   (baku: label dibiarkan).
6. Salin `.bin` hasil (dan `Labels_new.bin` bila dipakai) ke folder
   `LANGUAGES` setelah mencadangkan berkas asli.

Alur mengedit string:

1. Pilih **7 (Edit String)**.
2. Tentukan berkas `.bin` di `files/` yang akan diedit.
3. Tulis `Key` acuan. Nilainya bisa dilihat di kolom `Key` pada tabel hasil
   Export.
4. Kosongkan salah satu isian bila tidak ingin mengubahnya:
   - isi **Teks baru** untuk mengganti `Text`,
   - isi **Label baru** untuk mengganti `Label`.
5. Tentukan nama hasil. Untuk perubahan teks, bakunya
   `English_edited.bin`. Untuk perubahan label saja, bakunya
   `Labels_edited.bin`.
6. Salin hasilnya ke folder `LANGUAGES` setelah mencadangkan berkas asli.

Edit String tidak mengubah jumlah entri, urutan tabel, atau nilai `Key`.
Setelah mengedit teks, Export ulang `.bin` hasilnya bila ingin melihat
perubahan di tabel.

Setelah menambah atau menghapus string, **Export ulang** `.bin` hasilnya bila
ingin melihat perubahan di tabel. `Index` baris sesudah titik sisip atau titik
hapus ikut bergeser, karena tabel harus tetap urut menurut `Key`.

### Lewat argumen

Karena folder `files/` jadi patokan, perintahnya jadi pendek:

```
python main.py export
python main.py export --format csv
python main.py import English.xlsx
python main.py check English.xlsx
python main.py to-txt English.xlsx
python main.py from-txt English.txt --base English.xlsx
python main.py add-string --label MY_STRING --text "Teks baru"
python main.py remove-string --key 0x1234ABCD
python main.py edit-string --bin English.bin --key 0x1234ABCD --text "Teks baru"
python main.py info English_new.bin
python main.py verify "*.bin"
```

Aturan path: **nama berkas saja** dicari di `files/`. Path yang mengandung
folder (`D:\kerja\English.bin`) dipakai apa adanya.

```
python main.py export --bin German.bin --labels Labels.bin
python main.py import English.xlsx -o English_final.bin
python main.py to-txt English.xlsx -o kerja\English.txt
python main.py from-txt kerja\English.txt --base English.xlsx
python main.py add-string --bin English.bin --label MY_STRING --text "Teks baru" --labels Labels.bin
python main.py add-string --key 0x1234ABCD --text "Teks baru" -o English_tambah.bin
python main.py remove-string --bin English.bin --key 0x1234ABCD --labels Labels.bin -o English_hapus.bin
python main.py edit-string --bin English.bin --key 0x1234ABCD --label LABEL_BARU
python main.py edit-string --target "D:\kerja\English.bin" --key 0x1234ABCD --text "Teks baru"
python main.py info "D:\kerja\English.bin"
```

### Edit String tanpa subperintah

`edit-string` juga bisa dipanggil langsung, tanpa nama perintah:

```
python main.py --target "C:/Path/English.bin" --key 0x12345678 --text "Teks Baru"
python main.py --target "C:/Path/English.bin" --key 0x12345678 --label LABEL_BARU
python main.py --target "C:/Path/English.bin" --key 0x12345678 --label LABEL_BARU --text "Teks Baru"
```

Bedanya `--target` dan `--bin`:

- `--target` menerima path bebas, termasuk berkas di luar folder `files/`.
  `Labels.bin` dicari di folder yang sama dengan target; bila tidak ada,
  dipakai `files/Labels.bin`.
- `--bin` menerima nama/path berkas di dalam `files/`. Sumber dan label
  diambil dari sana.

Hasil baku:

| Perubahan           | Berkas hasil                        |
| ------------------- | ----------------------------------- |
| `--text`            | `<nama>_edited.bin` di folder sumber |
| `--label`           | `Labels_edited.bin` di folder label  |
| `--text` + `--label`| keduanya                            |

`-o/--output` menentukan hasil `.bin`. Untuk edit label saja, `-o` dipakai
sebagai nama hasil label. `--labels-out` selalu khusus untuk hasil label dan
`--labels` untuk memilih `Labels.bin` sumber.

| Perintah        | Guna                               | Hasil baku                  |
| --------------- | ---------------------------------- | --------------------------- |
| `export`        | `.bin` → tabel                     | `files/<nama>.xlsx`         |
| `import`        | tabel → `.bin` baru                | `files/<tabel>_new.bin`     |
| `check`         | validasi tabel, tanpa menulis      | —                           |
| `to-txt`        | tabel → `.txt` (`index, text`)     | `files/<tabel>.txt`         |
| `from-txt`      | `.txt` + tabel dasar → tabel baru  | `files/<txt>_new.<format>`  |
| `add-string`    | tambah satu entri baru ke `.bin`   | `files/<nama>_new.bin`      |
| `remove-string` | hapus entri menurut `Key`          | `files/<nama>_new.bin`      |
| `edit-string`   | ubah teks/label satu `Key`         | `<nama>_edited.bin` / `Labels_edited.bin` |
| `info`          | header dan tata letak berkas       | —                           |
| `verify`        | uji `parse → rebuild` byte-identik | —                           |

`--bin` dan `--labels` opsional; bakunya `files/English.bin` dan
`files/Labels.bin` bila ada. `--force` pada import tetap menulis hasil walau
ada error validasi.

`to-txt` wajib diberi tabel yang sudah ada. `from-txt` wajib diberi `--base`,
yaitu tabel empat kolom yang menyumbang `Index`, `Key`, dan `Label`. Format
hasil mengikuti tabel dasar: dasar `.xlsx` menghasilkan `.xlsx`, dasar `.csv`
menghasilkan `.csv`.

`add-string` menerima `--key` heksadesimal atau, bila `--key` dikosongkan,
menghitung key dari `--label`. `--text` ditulis apa adanya; tambahkan
`--escape` bila ingin `\xHH` di dalamnya ditafsirkan sebagai byte kontrol.
`--labels` opsional: label baru ikut ditulis ke salinan `Labels.bin`
(`--labels-out` untuk menentukan namanya).

`remove-string` wajib diberi `--key` (boleh diulang untuk beberapa key).
`--labels` opsional: key yang sama ikut dihapus dari salinan `Labels.bin`
(`--labels-out` untuk menentukan namanya). Tanpa `--labels`, label dibiarkan.

---

## Bentuk tabel

Empat kolom, urutan tetap:

| Index | Key        | Label | Text |
| ----- | ---------- | ----- | ---- |
| 0     | 0x00000474 | AT    | @    |
| 1     | 0x0000AC49 | GPS   | GPS  |
| 2     | 0x0000BF9C | LAP   | LAP  |
| 5     | 0x000144AB | Back  | Back |

- **Index** — nomor urut entri pada berkas, `0 .. jumlah-1`. Kunci baris.
- **Key** — nilai `u32` dari tabel entri, heksadesimal. Identitas entri.
- **Label** — nama simbol dari `Labels.bin`, dicocokkan lewat `Key`. Kosong
  bila `Key` tidak punya label (biasanya isi mod).
- **Text** — teks yang tersimpan di berkas bahasa, encoding Latin-1.
  **Hanya kolom ini yang seharusnya diubah.**

Pada `.xlsx` ada lembar tambahan `Meta` berisi SHA-256 berkas sumber, jumlah
entri, dan posisi tabel. Lembar ini dibaca ulang saat import untuk memastikan
tabel memang berasal dari `.bin` yang sama.

### Soal `Label` kosong

Tool ini membiarkan `Label` kosong bila `Key` tidak punya nama di
`Labels.bin`. Itu tidak menimbulkan masalah apa pun.

Kolom `Label` tidak pernah dipakai saat import. Ia hanya dipakai untuk
menyebut baris di pesan error. Sudah diuji tiga variasi pada tabel yang sama
— `Label` kosong, `Label` diisi `Key`, `Label` diisi teks sembarang —
ketiganya menghasilkan `.bin` dengan **SHA-256 identik**.

Karena itu `Label` kosong sengaja dibiarkan kosong: ia menandai baris yang
tidak punya nama simbol di `Labels.bin`, yaitu isi mod. Kalau diisi `Key`,
tanda itu hilang dan isinya cuma mengulang kolom `Key` di sebelahnya.

### Aturan yang tidak boleh dilanggar

- **Jangan urut ulang baris.** Game melakukan pencarian biner pada kolom key
  yang terurut naik; urutan tabel adalah bagian dari format.
- **Jangan ubah/hapus nilai `Key`.** Sama alasannya.
- **Jangan ubah `Index`.** Import memakai kolom ini untuk mencocokkan baris.
- **Jangan tambah atau hapus baris di tabel.** Untuk menambah, menghapus, atau
  mengubah satu entri, pakai menu **5 (Tambah String)**, **6 (Hapus String)**,
  atau **7 (Edit String)**; tool yang mengurutkan dan menghitung ulang offset.
  Baris yang tidak ada di tabel akan memakai teks asli.
- Setelah menambah atau menghapus string, **Export ulang** `.bin` hasilnya.
  `Index` baris sesudah titik sisip atau titik hapus bergeser, jadi tabel lama
  tidak lagi cocok untuk `.bin` yang sudah berubah jumlah entrinya.
- Teks harus bisa ditulis sebagai byte tunggal (Latin-1). Karakter di luar itu
  ditolak dengan pesan error, bukan diganti diam-diam.
- Teks tidak boleh mengandung byte NUL.

Filter (`AutoFilter`) dan pengurutan _tampilan_ di Excel aman dipakai — yang
penting baris tidak dipindah atau dihapus saat menyimpan.

---

## Jembatan TXT (`index, text`)

Dua menu ini bekerja dengan dua kolom saja, supaya teks mudah diedit terpisah
tanpa membawa `Key`, `Label`, atau lembar `Meta`.

| Menu | Perintah    | Arah                                  |
| ---- | ----------- | ------------------------------------- |
| 3    | `to-txt`    | tabel `.xlsx`/`.csv` → `.txt`         |
| 4    | `from-txt`  | `.txt` + tabel dasar → tabel baru     |

**Tabel harus ada dulu.** `to-txt` memilih satu tabel yang sudah dibuat lewat
Export. `from-txt` memilih satu `.txt` dan satu tabel dasar; `Index`, `Key`,
dan `Label` disalin dari tabel dasar, hanya `Text` yang diambil dari `.txt`.
Karena itu `from-txt` tidak bisa membuat tabel dari nol.

### Bentuk berkas

```
0, @
1, GPS
2, LAP
133, Defeat Ho Seun \x82Sonny\x83
```

- Koma **pertama** adalah pemisah. Satu spasi setelah koma adalah pemisah,
  bukan bagian teks; sisa baris dianggap teks apa adanya.
- Teks boleh mengandung koma (`1, teks, dengan, koma`).
- Spasi di awal teks dipertahankan (`2,  spasi depan` → teks `" spasi depan"`).
- Berkas ditulis UTF-8 tanpa BOM. Saat membaca, BOM, CRLF, baris kosong,
  baris komentar `#`, dan header opsional `Index, Text` diterima.
- `Index` tidak boleh duplikat, negatif, atau tidak ada di tabel dasar.

### Escape karakter kontrol

Sebagian teks memakai byte kontrol untuk simbol yang digambar font game
(`0x81` ™, `0x82`/`0x83` tanda kutip, `0x84` pemisah, `0x85` apostrof).
Byte itu **tidak ditulis mentah** di `.txt`, karena `0x85` dan `0x0B`
dianggap akhir baris oleh banyak alat pembaca teks. Yang ditulis adalah
escape:

| Teks asli        | Di `.txt` |
| ---------------- | --------- |
| `\` (garis miring) | `\\`    |
| baris baru       | `\n`      |
| carriage return  | `\r`      |
| tab              | `\t`      |
| byte `0x85`      | `\x85`    |

Contoh nyata: `Defeat Ho Seun \x82Sonny\x83`. Escape tak dikenal (mis.
`\q`) atau `\x` yang tidak diikuti dua digit hex **ditolak** dengan pesan
baris yang jelas, bukan diubah diam-diam. Saat kembali ke tabel, escape
dikembalikan menjadi byte aslinya, sehingga teks yang tidak diedit tetap
identik.

### Aturan hasil

- `Index` yang **tidak ada** di `.txt` memakai teks dari tabel dasar, dan
  tool memberi peringatan beserta daftar `Index`-nya.
- `Index` yang **tidak ada** di tabel dasar ditolak; tidak ada baris baru
  yang bisa masuk tanpa `Key`.
- Seluruh baris tabel dasar tetap ditulis, urutannya tidak berubah, dan
  `Key`/`Label` tidak disentuh.
- Teks baru divalidasi dulu (Latin-1, tanpa NUL) sebelum ada berkas ditulis.
- `to-txt` membaca ulang `.txt` yang baru ditulis dan memastikan seluruh isinya
  sama dengan tabel; `from-txt` membaca ulang tabel hasil dan membandingkan
  keempat kolomnya. Tabel dasar tidak pernah ditimpa.
- Kalau `.txt` tujuan sudah ada, tool minta konfirmasi sebelum menimpanya
  (baku: tidak menimpa).

---

## Tambah string baru

Menu **5** menambahkan satu entri baru: `Key`, `Label`, dan `Text`. Yang
disimpan di berkas bahasa hanya `Key` dan `Text`; `Label` adalah nama bantu
untuk kolom `Label`.

### Mekanisme

1. Entri baru ditambahkan ke daftar.
2. Seluruh daftar diurutkan menurut `Key` (game memakai pencarian biner).
3. `COUNT` di header, alamat entri terakhir, penunjuk akhir blob, dan offset
   tiap entri dihitung ulang.
4. Seluruh `Key` dan `Text` lama dibandingkan satu per satu dengan sumber.
5. Berkas hasil diurai ulang, lalu `parse → rebuild` harus byte-identik.

Karena tabel digeser, `Index` entri sesudah titik sisip berubah. Itu normal
dan bukan kerusakan; Export ulang `.bin` hasilnya untuk mendapatkan tabel
yang sesuai.

### Key dan Label

- `Key` adalah angka `u32` heksadesimal, mis. `0x1234ABCD`, dan tidak boleh
  sudah ada di berkas.
- Kalau `Key` dikosongkan, tool menghitungnya dari `Label` dengan algoritma
  hash NFS: mulai `0xFFFFFFFF`, lalu `hasil = hasil * 0x21 + byte karakter`.
- `Label` tidak ditulis ke `English.bin`. Kalau `Labels.bin` tersedia, tool
  menawarkan salinan `Labels_new.bin` yang memuat pasangan `Key → Label`
  baru, supaya label itu muncul lagi saat Export.
- `Label` dan `Text` mengikuti encoding Latin-1 dan tidak boleh mengandung
  NUL.

### Yang perlu diingat

- Entri baru hanya berguna kalau ada kode game/mod yang memakai `Key`
  tersebut. Menambah string tidak otomatis memunculkannya di menu game.
- Lakukan penambahan pada setiap berkas bahasa yang perlu menampilkannya.
  `Labels.bin` dipakai bersama, jadi cukup ditambah sekali.
- Sebaiknya tambahkan string **sebelum** mulai mengedit teks. Setelah jumlah
  entri berubah, tabel lama tidak bisa dipakai untuk `.bin` yang baru.
- Pengujian di tool ini bersifat struktural (header, offset, urutan, isi).
  Uji juga di game dengan salinan berkas asli sebagai cadangan.

### Lewat argumen

```
python main.py add-string --label MY_STRING --text "Teks baru"
python main.py add-string --key 0x1234ABCD --text "Teks baru" -o English_tambah.bin
python main.py add-string --label MY_STRING --text "Halo\x82dunia\x83" --escape --labels Labels.bin
```

Tanpa `--labels`, label hanya ditampilkan di laporan. Dengan `--labels`,
label baru ikut ditulis ke `Labels_new.bin` (bisa diubah dengan
`--labels-out`).

---

## Hapus string

Menu **6** menghapus entri menurut `Key`. Satu operasi bisa menghapus satu
atau beberapa key sekaligus lewat argumen.

### Mekanisme

1. Seluruh `Key` yang diminta diperiksa: harus ada, berupa `u32`, dan tidak
   duplikat.
2. Entri itu dibuang dari daftar; entri lain tidak diubah.
3. Tabel menyusut 8 byte per entri, sehingga awal blob dan offset seluruh
   entri tersisa digeser.
4. Teks yang tidak lagi dipakai oleh key mana pun ikut dibuang dari blob.
5. `COUNT` di header, alamat entri terakhir, dan penunjuk akhir blob dihitung
   ulang.
6. Seluruh `Key` dan `Text` yang tersisa dibandingkan dengan sumber; berkas
   hasil diurai ulang dan `parse → rebuild` harus byte-identik.

`Index` entri sesudah titik hapus bergeser turun. Itu normal dan bukan
kerusakan; Export ulang `.bin` hasilnya untuk mendapatkan tabel yang sesuai.

### Key dan Label

- Key yang tidak ada di berkas ditolak; tidak ada berkas yang ditulis.
- Kalau dua `Key` memakai offset teks yang sama, teks itu tetap disimpan
  selama salah satunya masih ada.
- `Label` tidak disimpan di berkas bahasa. Kalau `Labels.bin` tersedia, tool
  menawarkan penghapusan label dari salinan `Labels_new.bin`. Baku: label
  dibiarkan, karena `Labels.bin` dipakai bersama oleh semua berkas bahasa.
- Seluruh entri tidak boleh dihapus sekaligus.

### Yang perlu diingat

- Hapus hanya key yang memang tidak dipakai lagi. Kode game/mod yang masih
  memakai key tersebut tidak akan menemukan teksnya.
- Lakukan penghapusan pada setiap berkas bahasa yang memuat key itu.
- Label yang dibiarkan tidak memengaruhi isi berkas bahasa.
- Pengujian di tool ini bersifat struktural (header, offset, urutan, isi).
  Uji juga di game dengan salinan berkas asli sebagai cadangan.

### Lewat argumen

```
python main.py remove-string --key 0x1234ABCD
python main.py remove-string --key 0x1234ABCD --key 0x00000474 -o English_hapus.bin
python main.py remove-string --key 0x1234ABCD --labels Labels.bin
```

Tanpa `--labels`, label dibiarkan. Dengan `--labels`, key yang sama ikut
dihapus dari salinan `Labels_new.bin` (bisa diubah dengan `--labels-out`).

---

## Edit string

Menu **7** mengubah satu string yang sudah ada. Acuannya `Key`; yang boleh
diubah adalah `Text`, `Label`, atau keduanya. Jumlah entri tidak berubah.

### Dua sumber berkas

| Opsi       | Arti                                                        |
| ---------- | ----------------------------------------------------------- |
| `--target` | path bebas, boleh jauh di luar folder `files/`              |
| `--bin`    | nama berkas di dalam `files/`                               |

Untuk `--target`, `Labels.bin` dicari di folder yang sama dengan target. Bila
tidak ada, dipakai `files/Labels.bin`. Untuk `--bin`, sumber dan label
diambil dari `files/`. `--labels` selalu menimpa pilihan otomatis itu.

### Mekanisme

1. `Key` diperiksa: harus ada di berkas bahasa, berupa `u32`, dan bukan nol.
2. Bila `Text` diisi, hanya teks milik key itu yang diganti.
3. Bila key itu berbagi offset teks dengan key lain, entrinya dipindahkan ke
   offset baru supaya teks pasangannya tidak ikut berubah.
4. Bila `Label` diisi, key yang sama diperbarui di `Labels.bin`. Kalau belum
   ada, key itu ditambahkan; tabel label tetap urut menurut `Key`.
5. Urutan tabel berkas bahasa dan seluruh nilai `Key` dipertahankan.
6. Hasil diurai ulang: teks/label lain harus sama persis, hasil hanya berubah
   pada key yang diminta, lalu `parse → rebuild` harus byte-identik.

### Hasil baku

| Perubahan            | Hasil                                               |
| -------------------- | --------------------------------------------------- |
| `--text`             | `<nama>_edited.bin` di folder sumber                |
| `--label`            | `Labels_edited.bin` di folder `Labels.bin`          |
| `--text` + `--label` | keduanya                                           |

`-o/--output` menentukan hasil `.bin`. Pada edit label saja, `-o` dipakai
sebagai nama hasil label. `--labels-out` khusus untuk hasil label.

### Yang perlu diingat

- Minimal satu dari `--text` atau `--label` harus diisi.
- `--label` yang kosong atau hanya spasi ditolak.
- Label hanya bisa disimpan bila `Labels.bin` tersedia.
- Edit teks tidak menggeser `Index`, karena jumlah dan urutan entri tetap.
- Berkas sumber tidak pernah ditimpa.

### Lewat argumen

```
python main.py edit-string --bin English.bin --key 0x1234ABCD --text "Teks baru"
python main.py edit-string --bin English.bin --key 0x1234ABCD --label LABEL_BARU
python main.py edit-string --bin English.bin --key 0x1234ABCD --label LABEL_BARU --text "Teks baru"
python main.py edit-string --target "D:\kerja\English.bin" --key 0x1234ABCD --text "Teks baru"
```

Bentuk langsung, tanpa subperintah:

```
python main.py --target "C:/Path/English.bin" --key 0x12345678 --text "Teks Baru"
python main.py --target "C:/Path/English.bin" --key 0x12345678 --label LABEL_BARU
python main.py --target "C:/Path/English.bin" --key 0x12345678 --label LABEL_BARU --text "Teks Baru"
```

`--escape` menafsirkan `\xHH` di `--text` sebagai byte kontrol.

---

## Karakter khusus

Tool ini **tidak pernah** mengganti karakter menjadi `?`. Teks dibaca sebagai
byte Latin-1 apa adanya; saat import, karakter yang tidak bisa ditulis sebagai
satu byte ditolak dengan error.

Sebagian berkas bahasa memakai byte kontrol untuk huruf yang digambar oleh
font game. Contohnya `Polish.bin` memuat byte `0x05`, `0x07`, dan `0x19`
(pemetaan font NFSMW untuk ą, ć, ę). Excel tidak menerima byte kontrol di
dalam sel, jadi saat export ke `.xlsx` byte itu ditulis dengan konvensi OOXML
`_x0007_`. Saat import, pola tersebut dikembalikan menjadi byte aslinya,
sehingga hasilnya tetap byte-identik — sudah diuji sampai berkasnya dibuka
dan disimpan ulang oleh Excel.

Yang perlu diketahui:

- Di Excel, `_x0007_` **tampil sebagai karakter tak terlihat**. Jangan
  menghapus atau memindahkannya saat mengedit baris tersebut.
- Di Excel, byte `0x81`–`0x9F` (mis. `™`, tanda kutip melengkung) bisa
  **tampil sebagai `?`** karena font sel tidak punya glyph-nya, padahal isi
  sel tetap utuh. Jangan menganggap `?` itu karakter rusak lalu menimpanya;
  setelah disimpan dan diimpor, teksnya tetap terbaca sebagai byte aslinya.
  Kalau ragu, pakai alur TXT yang menulis byte tersebut sebagai
  `\x81`–`\x9F` sehingga terlihat jelas.
- Teks yang memang berisi pola `_xHHHH_` (mis. `_x0041_`) dilindungi saat
  export. Excel membuang perlindungan itu saat menyimpan, dan pola dengan
  kode `0x00`–`0x1F` akan dibaca sebagai byte kontrol. Teks game NFSMW tidak
  memakai pola seperti ini (sudah diperiksa di semua berkas).
- **CSV** menyimpan byte kontrol apa adanya, tetapi Excel bisa mengubah teks
  yang mirip tanggal saat menyimpan (mis. `5-1-0` menjadi `5/1/2000`).
  Karena itu `.xlsx` lebih aman untuk mengedit.
- Kalau CSV disimpan lewat `Save As > CSV (Comma delimited)`, Excel memakai
  code page lama sehingga berkasnya bukan UTF-8 lagi. Import akan menolaknya
  dengan pesan jelas. Pilih **CSV UTF-8 (Comma delimited)**.

---

## Jaminan keamanan

- Berkas `.bin` sumber **tidak pernah ditimpa**. Hasil selalu berkas baru.
- Bila ada error validasi, import berhenti sebelum menulis apa pun
  (`--force` untuk memaksa).
- Setelah menulis, hasil diurai ulang dan diperiksa:
  - jumlah entri sama,
  - daftar `Key` persis sama dan tidak bergeser,
  - tiap `Text` terbaca persis seperti yang ditulis.
- Untuk **Tambah String**, pemeriksaannya:
  - jumlah entri bertambah tepat satu,
  - seluruh `Key` dan `Text` lama tetap sama,
  - entri baru terbaca persis,
  - kolom `Key` tetap terurut naik dan tidak duplikat,
  - `parse → rebuild` byte-identik.
- Untuk **Hapus String**, pemeriksaannya:
  - jumlah entri berkurang tepat sebanyak key yang diminta,
  - key yang dihapus tidak ada lagi di hasil,
  - seluruh `Key` dan `Text` yang tersisa tetap sama,
  - kolom `Key` tetap terurut naik dan tidak duplikat,
  - `parse → rebuild` byte-identik.
- Untuk **Edit String**, pemeriksaannya:
  - jumlah entri dan daftar `Key` tidak berubah,
  - hanya teks/label milik key yang diminta yang berbeda,
  - teks pasangan yang berbagi offset tidak ikut berubah,
  - label lain di `Labels.bin` tetap sama,
  - kolom `Key` tetap terurut naik dan tidak duplikat,
  - `parse → rebuild` byte-identik.
- `Verifikasi: LOLOS` berarti syarat-syarat di atas terpenuhi.

Yang ditolak, dan sudah diuji:

```
Key diubah             Ditolak: Key tidak cocok: tabel 0xDEADBEEF, berkas 0x00000474
karakter non-Latin-1   Ditolak: 'latin-1' codec can't encode characters in position 0-1
Index duplikat         Ditolak: Index muncul lebih dari sekali
header diubah          Ditolak: header tabel tidak cocok
```

---

## Catatan format berkas `.bin`

Struktur ini sudah diverifikasi lewat uji round-trip **byte-identik** pada 14
berkas bahasa (`English`, `German`, `French`, `Italian`, `Spanish`, `Dutch`,
`Polish`, `Swedish`, `Finnish`, `Danish`, `Chinese`, `Korean`, `Largest`,
`Labels`), termasuk satu berkas original yang belum pernah di-repack.

```
offset  isi
------  ------------------------------------------------------------
0x0000  u32 x6 header
          [0] ID blok STRBlocks (0x00039000)
          [1] penunjuk akhir blob string (+ delta tetap per berkas)
          [2] konstanta 0x20
          [3] COUNT jumlah entri
          [4] penunjuk blok tabel
          [5] alamat entri terakhir (= base - 8)
0x0018  blok "GLOBAL" (opaque, disalin apa adanya)
hdr[4]  u64 sentinel {0,0}
+8      tabel entri: COUNT x {u32 key, u32 offset}
base    blob string, tiap string diakhiri NUL
tail    blok resource font (FNTF/gMpB/padding) — opaque
```

Relasi yang berlaku:

```
table_start = hdr[4] + 8
base        = table_start + 8 * COUNT
alamat teks = base + offset
```

Poin yang mudah salah:

- Posisi tabel **tidak boleh di-hardcode**. Berkas di folder game memakai
  `0x182C`, berkas original yang lebih tua memakai `0x181C`. Selalu baca dari
  `hdr[4]`.
- `hdr[1]` bukan alamat absolut. Selisihnya terhadap akhir blob bervariasi
  antara −8 dan +7 antar berkas, jadi delta aslinya disimpan lalu digeser
  bersama blob.
- `hdr[0]` berisi `0x39000` di semua berkas yang diperiksa, yaitu ID blok
  `STRBlocks`. Nilainya tidak diubah saat rebuild.
- `hdr[5]` adalah alamat entri terakhir, yaitu `base - 8`, bukan awal blob.
  Saat entri ditambah atau dihapus, `base` bergeser 8 byte per entri sehingga
  `hdr[5]` ikut berubah.
- Menambah entri menggeser awal blob 8 byte, lalu teks baru diletakkan di
  akhir blob. Offset entri lama tidak berubah karena dihitung relatif
  terhadap awal blob yang baru.
- Menghapus entri menyusutkan tabel 8 byte per entri. Teks yang tidak dipakai
  lagi oleh key mana pun dibuang dari blob, dan offset entri tersisa digeser.
- Satu string disimpan sekali per offset unik. Dua `Key` boleh menunjuk offset
  yang sama. Saat teks salah satunya diedit, key itu dipindahkan ke offset
  baru supaya pasangannya tidak ikut berubah.
- Encoding teks adalah byte tunggal (Latin-1), **bukan** UTF-8. `English.bin`
  bawaan bahkan sudah kehilangan byte non-ASCII yang masih ada di `German.bin`
  (1079 kasus, mis. `ESPAOL` vs `ESPAÑOL`).
- `LanguageTextures.bin` di folder `LANGUAGES` bukan basis data string;
  `verify` akan melaporkannya sebagai error. Itu wajar.

---

## Struktur proyek

```
NFSMW Lang Tool/
├── main.py             # Menu + argumen CLI + penentuan folder files/
├── requirements.txt
├── README.md
├── files/              # Semua berkas kerja
└── lib/
    ├── nfsbin.py       # Baca / bangun ulang / verifikasi berkas .bin
    ├── nfstable.py     # Empat kolom, penggabungan Label, pembacaan tabel
    ├── nfsexport.py    # Merubah .bin menjadi xlsx/csv
    ├── nfsimport.py    # Merubah xlsx/csv menjadi .bin
    ├── nfstxt.py       # Jembatan tabel <-> .txt (index, text)
    ├── nfsadd.py       # Tambah string baru (key + label + text)
    ├── nfsremove.py    # Hapus string lama berdasarkan key
    ├── nfsedit.py      # Ubah teks dan/atau label satu key
    └── tui.py          # Tampilan terminal dan menu
```
