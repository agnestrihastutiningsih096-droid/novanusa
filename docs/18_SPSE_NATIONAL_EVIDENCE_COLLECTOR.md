# 18. SPSE National Evidence Collector

## Tujuan

SPSE National Evidence Collector v1 mengambil sample kecil data paket dari SPSE Nasional sebagai evidence pertama setelah SiRUP.

Collector ini dibuat untuk mendukung prinsip NovaNusa bahwa SiRUP adalah planning layer. Jika paket ditemukan di SPSE Nasional tender, non tender, atau darurat, maka catatan tersebut menjadi evidence bahwa paket sudah bergerak melewati SiRUP.

Collector ini tidak membuat opportunity score, AI score, atau kesimpulan bahwa paket masih peluang.

## Sumber Resmi

Sumber awal yang digunakan:

- `https://spse.inaproc.id/nasional/lelang`
- `https://spse.inaproc.id/nasional/nontender`
- `https://spse.inaproc.id/nasional/darurat`

Collector hanya mengambil halaman publik resmi, berjalan sekuensial, memakai limit kecil, dan tidak melewati autentikasi, CAPTCHA, rate limit, atau access control.

## Struktur Data

Raw HTML disimpan di:

- `data/evidence/spse/nasional/raw/`

Hasil parsing dan metadata disimpan di:

- `data/evidence/spse/nasional/parsed/`

Excel sample disimpan ke:

- `outputs/evidence/spse_national_sample.xlsx`

Kolom minimal parsed evidence:

- `source_url`
- `source_type`
- `package_code`
- `package_name`
- `institution_name`
- `stage_or_status`
- `hps_or_pagu`
- `fiscal_year`
- `collected_at`
- `evidence_level`
- `raw_file_path`

Metadata evidence mencatat URL, waktu pengambilan, file raw, hash raw HTML jika berhasil diambil, jumlah tabel, jumlah row parsed, collector, scope, dan access note.

## Keterbatasan

SPSE Nasional dapat mengubah layout HTML, query parameter, atau cara tabel dimuat. Jika tabel dimuat melalui JavaScript atau endpoint internal yang tidak muncul di HTML awal, collector tetap menyimpan raw HTML dan metadata, tetapi parsed row bisa kosong.

Field seperti tahun anggaran, HPS/pagu, instansi, atau tahapan bergantung pada kolom yang tersedia di halaman publik. Jika tidak tersedia di tabel HTML, field terkait akan kosong dan perlu enrichment dari halaman detail atau sumber resmi lanjutan.

Collector v1 adalah sample collector, bukan crawler massal.

## Hubungan Dengan SiRUP

Aturan evidence:

- Tender ditemukan di SPSE Nasional = evidence bahwa paket sudah bergerak melewati SiRUP.
- Non Tender ditemukan di SPSE Nasional = evidence bahwa paket sudah bergerak melewati SiRUP.
- Darurat ditemukan di SPSE Nasional = evidence bahwa paket sudah bergerak melewati SiRUP.

Collector ini tidak menyimpulkan paket masih peluang. Jika tidak ada match downstream, pernyataan yang benar tetap: belum ada evidence downstream yang ditemukan dalam sumber yang tersedia.

## Cara Menjalankan

Jalankan dari root project:

```powershell
python scripts/collect_spse_national_evidence.py --year 2026 --limit 50
```

Parameter utama:

- `--year`: hint/filter tahun anggaran.
- `--limit`: batas maksimum total row evidence yang disimpan.
- `--delay`: jeda antar request sumber resmi, default `1.5` detik.
- `--timeout`: timeout HTTP, default `30` detik.
- `--output`: path Excel output.

## Output

Output utama:

- Raw HTML per source di `data/evidence/spse/nasional/raw/`.
- CSV parsed evidence di `data/evidence/spse/nasional/parsed/spse_national_sample_<year>.csv`.
- Metadata JSON di `data/evidence/spse/nasional/parsed/spse_national_sample_<year>_metadata.json`.
- Workbook Excel di `outputs/evidence/spse_national_sample.xlsx`.

Workbook berisi:

- `parsed_evidence`
- `metadata`
- `methodology`

## Langkah Berikutnya

Langkah berikutnya setelah v1:

- Verifikasi apakah SPSE Nasional menyediakan endpoint resmi atau export resmi untuk tabel.
- Tambahkan parsing halaman detail paket jika masih publik dan diizinkan.
- Tambahkan linkage faktual ke SiRUP memakai RUP ID, package code, nama paket, instansi, nilai, dan tahun.
- Tambahkan manual review queue untuk match ambigu.
- Tambahkan collector LPSE prioritas setelah pola SPSE Nasional stabil.
