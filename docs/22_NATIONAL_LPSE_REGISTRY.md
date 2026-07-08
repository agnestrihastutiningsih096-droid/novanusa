# 22. National LPSE Registry Builder

Tujuan modul ini adalah membangun registry nasional LPSE Indonesia sebagai fondasi collector berikutnya. Registry ini hanya memakai sumber resmi publik, tidak melakukan crawling agresif, dan tidak membuat AI score atau opportunity score.

## Tujuan

- membangun daftar nasional LPSE resmi
- menyimpan provenance untuk setiap baris registry
- menyediakan dasar referensi untuk collector LPSE daerah, LPSE kementerian, dan mapping evidence berikutnya

## Sumber resmi

Sumber resmi utama:
- `https://eproc.lkpp.go.id/lpse/index`
- filter publik `propinsi`, `standardisasi`, `tipe`, `aktif`, `versi`, dan `keywords`
- halaman detail publik `http://eproc.lkpp.go.id/lpse/read/{id}/{slug}`

Sumber ini dipakai karena halaman SPSE Nasional `inaproc.id/lpse` terbukti menampilkan challenge perimeter di environment ini, sedangkan portal eProc LKPP tetap menyediakan registry publik yang dapat diaudit.

## Struktur Registry

Registry dibangun dari dua lapisan publik:
1. index LPSE eProc
2. halaman detail LPSE per item

Kolom minimal yang disimpan:
- `nama_lpse`
- `instansi`
- `kategori_instansi`
- `provinsi`
- `kabupaten_kota`
- `official_lpse_url`
- `domain`
- `https`
- `aktif`
- `dapat_diakses`
- `menggunakan_spse`
- `versi_spse`
- `portal_induk`
- `tanggal_pengecekan`
- `source_url`

Kolom tambahan provenance:
- `source_page`
- `source_page_number`
- `source_filter_provinsi`
- `source_note`

Jika suatu informasi tidak tersedia secara publik, nilai diisi `null`.

## Kategori LPSE

Kategori di registry bersifat operasional, bukan klaim legal final. Kategori umum yang dipakai:
- Kementerian
- Lembaga
- Pemerintah Provinsi
- Pemerintah Kabupaten
- Pemerintah Kota
- Perguruan Tinggi
- BUMN
- Lainnya atau tidak terklasifikasi

## Identifier

Primary identifier yang disarankan:
- `source_page` jika detail page tersedia
- `nama_lpse` + `provinsi` + `source_filter_provinsi` untuk deduplikasi lunak
- `official_lpse_url` jika publik dan terisi

`instansi` dipakai untuk human review, tetapi bukan identifier utama karena bisa berubah format penamaannya.

## Quality Rules

Aturan kualitas registry:
- satu baris merepresentasikan satu LPSE resmi
- no score
- no inferred opportunity
- provenance wajib tersimpan
- field publik yang tidak terverifikasi harus `null`
- duplicate dihitung berdasarkan kombinasi detail URL, nama, dan provinsi

## Provenance

Setiap baris membawa provenance minimal:
- halaman index asal
- nomor halaman index
- filter provinsi yang dipakai
- tanggal pengecekan
- detail page asal

Jika landing page LPSE berhasil diakses, status akses dan versi SPSE dapat diisi berdasarkan hasil probe publik yang sopan. Jika `official_lpse_url` kosong di halaman publik, field tersebut tetap `null`.

## Update Strategy

Registry ini sebaiknya diperbarui dengan pola:
1. muat halaman index publik
2. baca filter provinsi yang tersedia
3. crawl halaman per provinsi dan per halaman kecil
4. kunjungi detail page untuk provenance dan field publik tambahan
5. simpan CSV, JSON, raw HTML, dan summary spreadsheet

Regenerasi berkala cukup dilakukan saat:
- ada perubahan besar pada portal eProc
- registry LPSE digunakan sebagai input collector baru
- ada LPSE baru yang perlu ditangkap

## Cara Menjalankan

```bash
python scripts/build_lpse_registry.py
```

Output utama:
- `data/reference/lpse/lpse_registry.csv`
- `data/reference/lpse/lpse_registry.json`
- `outputs/reference/lpse_registry_summary.json`
- `outputs/reference/lpse_registry_summary.xlsx`

## Keterbatasan

- halaman publik dapat menampilkan `challenge` atau memerlukan beberapa filter agar registry lengkap
- versi SPSE tidak selalu tampil publik
- kategori instansi kadang harus diinferensikan dari nama instansi jika situs tidak menyediakan label eksplisit
- official LPSE URL sering kosong pada halaman publik, sehingga field itu boleh `null`
- akses publik bisa berubah dari waktu ke waktu
- registry ini bukan pengganti verifikasi manual untuk kasus yang sensitif

Jika field publik tidak dapat diverifikasi, tetap simpan baris registry dan tandai field itu `null`.
