# 23. LPSE Detail Collector v1

## Tujuan

Collector ini mengambil evidence detail paket dari LPSE resmi berdasarkan registry nasional LPSE. Fungsinya adalah memperdalam evidence setelah LPSE ditemukan di portal nasional, tanpa membuat scoring apa pun.

## Input

- `data/reference/lpse/lpse_registry.csv`
- `data/evidence/spse/nasional/parsed/spse_national_sample_2026.csv` jika tersedia

Collector hanya memakai LPSE yang punya `official_lpse_url` publik, `menggunakan_spse=True`, dan `dapat_diakses=True` jika field itu tersedia.

## Strategi Sampling

- Mulai dari sampel kecil, bukan crawling massal.
- Default verifikasi memakai `--limit-lpse 5` dan `--limit-packages 10`.
- Hanya mengunjungi halaman publik `lelang` dan `nontender` yang bisa diakses tanpa login.
- Setiap LPSE diproses secara berurutan dan setiap paket disimpan dengan bundle raw sendiri.

## Struktur Data

Kolom inti yang disimpan:

- `lpse_name`
- `lpse_url`
- `source_type`
- `package_code`
- `package_name`
- `institution_name`
- `hps_or_pagu`
- `stage_or_status`
- `method`
- `fiscal_year`
- `detail_url`
- `source_url`
- `collected_at`
- `raw_file_path`
- `evidence_level`

Kolom tambahan untuk evidence lanjutan:

- `schedule`
- `participants`
- `winner`
- `contract`
- `document_links`
- `raw_bundle_json`

## Provenance

Setiap baris detail punya manifest raw yang menunjuk ke:

- HTML daftar LPSE
- JSON DataTables publik
- HTML detail paket
- HTML subpage jika publik tersedia

Semua file raw disimpan di `data/evidence/lpse/raw/` dengan struktur per LPSE, tahun, jenis sumber, dan kode paket.

## Keterbatasan

- Tidak melakukan bypass autentikasi.
- Tidak mengakses endpoint yang butuh login.
- Tidak melakukan brute force parameter.
- Tidak menebak data yang tidak tampak publik.
- Jika detail tidak bisa diambil secara publik, baris diberi `LIMITED_PUBLIC_ACCESS`.

## Hubungan dengan SPSE Nasional

SPSE Nasional memberi evidence bahwa paket sudah muncul di ekosistem pengadaan nasional. Collector LPSE detail ini dipakai untuk mempertegas evidence per LPSE asal, detail paket, dan jejak publiknya.

## Hubungan dengan SiRUP

SiRUP adalah evidence perencanaan. LPSE detail adalah evidence eksekusi/disclosure publik. Keduanya tidak disamakan, dan collector ini tidak membuat asumsi bahwa paket pasti menang atau pasti lanjut kontrak.

## Cara Menjalankan

```bash
python scripts/collect_lpse_detail_evidence.py --year 2026 --limit-lpse 5 --limit-packages 10 --sleep 1
```

## Cara Membaca Hasil

- CSV parsed ada di `data/evidence/lpse/parsed/lpse_detail_sample_2026.csv`.
- Workbook ada di `outputs/evidence/lpse_detail_sample_2026.xlsx`.
- Ringkasan ada di `outputs/evidence/lpse_detail_sample_2026_summary.json`.
- `evidence_level=LPSE_PUBLIC_DETAIL_FOUND` berarti detail paket berhasil diambil dari halaman publik.
- `evidence_level=LIMITED_PUBLIC_ACCESS` berarti collector hanya mendapat sebagian evidence publik atau detail tidak tersedia.
