# 20. Targeted SPSE Evidence Expansion

## Masalah Coverage

SPSE National Evidence Collector v1 menghasilkan evidence SPSE Nasional, tetapi coverage awal masih kecil dan tidak selalu overlap dengan baris SiRUP yang dipilih untuk mapping.

Targeted SPSE Evidence Expansion v1 dibuat untuk memperluas coverage dengan keyword dari nama paket SiRUP yang paling sering muncul pada dataset lokal.

## Strategi Keyword

Keyword awal yang dipakai:

- komputer
- laptop
- printer
- cctv
- server
- jaringan
- kamera
- scanner
- perangkat
- alat

Collector mencari keyword tersebut pada nama paket SiRUP dan menggunakan keyword yang sama untuk menandai evidence SPSE yang relevan.

## Sumber Resmi

Sumber resmi yang menjadi acuan expansion tetap SPSE Nasional:

- `https://spse.inaproc.id/nasional/lelang`
- `https://spse.inaproc.id/nasional/nontender`
- `https://spse.inaproc.id/nasional/darurat`

V1 menjaga scope tetap kecil dan audit-friendly. Jika live keyword query tidak stabil, collector tidak memaksa crawling massal dan tetap memakai evidence resmi yang sudah tersedia di project sebagai fallback keyword-tagged evidence.

## Batasan Legal dan Etis

- Hanya sumber publik resmi yang dipakai.
- Tidak melewati autentikasi, CAPTCHA, atau access control.
- Tidak melakukan crawling massal.
- Tidak membuat opportunity score.
- Tidak menyimpulkan bahwa paket masih peluang.

## Struktur Output

Raw evidence disimpan di:

- `data/evidence/spse/nasional/raw/targeted/`

Parsed evidence disimpan di:

- `data/evidence/spse/nasional/parsed/spse_targeted_2026.csv`

Workbook output disimpan di:

- `outputs/evidence/targeted_spse_evidence_expansion.xlsx`

Summary JSON disimpan di:

- `outputs/evidence/targeted_spse_evidence_expansion_summary.json`

Kolom penting pada CSV:

- `source_url`
- `source_type`
- `keyword`
- `matched_keywords`
- `package_code`
- `package_name`
- `institution_name`
- `stage_or_status`
- `hps_or_pagu`
- `fiscal_year`
- `collected_at`
- `evidence_level`
- `raw_file_path`

## Cara Menjalankan

```powershell
python scripts/expand_spse_evidence_targeted.py --year 2026
```

## Cara Membaca Hasil

- `SPSE_TARGETED_FOUND` berarti row dipakai sebagai evidence SPSE yang ditag berdasarkan keyword SiRUP.
- `keyword` menunjukkan keyword utama yang memicu row.
- `matched_keywords` menunjukkan semua keyword yang cocok pada row itu.
- `raw_file_path` menunjuk ke file raw evidence yang dipakai untuk audit.

Output targeted ini dipakai sebagai input tambahan untuk mapper SiRUP -> SPSE evidence agar baris SiRUP yang relevan punya peluang lebih besar mendapat evidence status `SPSE_FOUND` atau minimal `NEEDS_MANUAL_REVIEW`.
