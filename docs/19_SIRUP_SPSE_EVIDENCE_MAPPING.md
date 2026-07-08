# 19. SiRUP to SPSE Evidence Mapping

## Tujuan

Modul ini mencocokkan paket SiRUP dengan evidence SPSE Nasional yang sudah dikumpulkan di NovaNusa.

Tujuannya adalah menghubungkan data perencanaan SiRUP dengan evidence eksekusi publik dari SPSE Nasional, tanpa membuat opportunity score atau AI score.

## Input

Input utama:

- Data SiRUP yang tersedia di project, jika ada.
- `data/evidence/spse/nasional/parsed/spse_national_sample_2026.csv`

Sumber SiRUP yang dipakai script adalah DuckDB lokal yang sudah digunakan oleh pipeline lain di repo, dengan fallback ke lokasi default yang sama selama file tersedia.

## Matching Strategy

Matching dilakukan bertingkat:

1. Exact

Cocok jika kode RUP atau kode paket SiRUP sama dengan `spse_package_code`.

2. Strong

Dipakai jika kombinasi berikut cukup kuat:

- nama paket mirip,
- instansi sama atau sangat mirip,
- tahun sama,
- nilai pagu/HPS mendekati.

3. Weak

Dipakai untuk kandidat yang belum cukup kuat dan harus diperiksa manual.

4. No match

Dipakai jika tidak ada evidence SPSE yang memadai.

Script ini tidak menghitung skor peluang. Tidak ada opportunity score. Tidak ada AI score.

## Evidence Status

Output `evidence_status` memakai nilai berikut:

- `SPSE_FOUND`
- `PLANNED_ONLY`
- `NEEDS_MANUAL_REVIEW`

Aturan pemakaiannya:

- `exact` dan `strong` -> `SPSE_FOUND`
- `weak` -> `NEEDS_MANUAL_REVIEW`
- `no_match` -> `PLANNED_ONLY`

## Keterbatasan

- Kualitas hasil sangat bergantung pada kesamaan nama paket, nama instansi, dan struktur kode dari dua sumber.
- SPSE Nasional sample v1 masih kecil, jadi tidak semua paket SiRUP akan punya pasangan.
- Jika SiRUP dan SPSE memakai nama paket yang berbeda secara signifikan, hasil bisa turun ke `weak` atau `no_match`.
- `PLANNED_ONLY` hanya berarti belum ada evidence SPSE yang cocok di input yang tersedia, bukan bukti bahwa paket belum bergerak.

## Cara Menjalankan

Jalankan dari root project:

```powershell
python scripts/map_sirup_to_spse_evidence.py --year 2026 --limit 1000
```

Parameter utama:

- `--year`: filter tahun target.
- `--limit`: jumlah maksimum baris SiRUP yang dipetakan.
- `--sirup-db`: path DuckDB SiRUP jika ingin override lokasi default.
- `--evidence-file`: file evidence SPSE CSV jika ingin override input default.
- `--output`: file Excel output.
- `--summary`: file JSON ringkasan output.

## Cara Membaca Output

Output utama:

- `outputs/evidence/sirup_spse_evidence_mapping.xlsx`
- `outputs/evidence/sirup_spse_evidence_mapping_summary.json`

Workbook Excel berisi sheet:

- `mapping`: hasil pemetaan baris demi baris.
- `methodology`: ringkasan aturan kerja.
- `summary`: ringkasan input dan kategori match.

Kolom penting di sheet `mapping`:

- `sirup_package_id`
- `sirup_package_name`
- `sirup_institution_name`
- `sirup_pagu`
- `spse_package_code`
- `spse_package_name`
- `spse_institution_name`
- `spse_hps`
- `spse_source_type`
- `spse_stage_or_status`
- `match_level`
- `match_reason`
- `evidence_status`
- `evidence_source_url`
- `collected_at`

Interpretasi praktis:

- `SPSE_FOUND` berarti paket SiRUP punya evidence SPSE Nasional.
- `PLANNED_ONLY` berarti belum ada pasangan evidence yang cocok dalam input yang tersedia.
- `NEEDS_MANUAL_REVIEW` berarti ada kandidat, tetapi belum cukup kuat untuk diputuskan otomatis.
