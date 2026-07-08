# Manual Procurement Evidence Collection Guide

This guide explains how to manually collect public procurement evidence files for crosschecking SiRUP planning rows against actual procurement activity.

SiRUP is a planning source. SiRUP alone is not proof that procurement is still open, not yet purchased, or not progressed. The crosscheck workflow only marks `PLANNING_ONLY_SIRUP` when no matching local evidence file was found.

## Folder Structure

Place manually downloaded files in the matching folder:

- `data/evidence/spse/` for SPSE Nasional search exports, tender pages, or process listings
- `data/evidence/lpse/` for LPSE-specific tender/non-tender exports or saved pages
- `data/evidence/epurchasing/` for e-purchasing or katalog evidence
- `data/evidence/contracts/` for contract, berkontrak, or tanda tangan kontrak evidence
- `data/evidence/winners/` for pemenang or award result evidence

Keep original downloaded files intact. If you clean or summarize a file, save the cleaned version separately and keep the source file beside it.

## Evidence Files Needed

Useful evidence files include manually downloaded CSV, XLSX, HTML, or JSON files showing one or more of these facts:

- SPSE/LPSE tender or non-tender process exists
- package is in evaluation, announcement, sanggah, or other tender stage
- pemenang exists
- pemenang berkontrak or contract exists
- tanda tangan kontrak exists
- e-purchasing or katalog transaction/process exists
- package is cancelled, failed, or dibatalkan

Do not scrape websites automatically. Download public files manually from official pages or export features where available.

## File Naming

Use descriptive filenames so the crosscheck script can discover likely evidence files automatically.

Recommended pattern:

`YYYYMMDD_source_scope_status_keyword.ext`

Examples:

- `20260705_spse_nasional_tender_alkes_may_june_2026.xlsx`
- `20260705_lpse_dki_pemenang_alkes_2026.csv`
- `20260705_epurchasing_katalog_alkes_rsud_2026.xlsx`
- `20260705_contracts_kemkes_pemenang_berkontrak_2026.html`
- `20260705_winners_rsud_cathlab_2026.csv`

Include one of these words when possible: `spse`, `lpse`, `tender`, `non_tender`, `epurchasing`, `e-purchasing`, `katalog`, `pemenang`, `kontrak`, `berkontrak`, `pengumuman`, or `sanggah`.

If a file has a generic name, pass it explicitly with `--evidence-files` when running the script.

## Useful Fields

The strongest crosscheck fields are:

- RUP ID
- package ID / tender ID / kode tender / kode paket
- package name / nama paket
- institution / KLDI / satker / work unit
- budget / pagu / HPS / contract value
- year / fiscal year / tender year
- procurement method
- stage / status / tahapan
- winner / pemenang
- contract status / berkontrak / tanda tangan kontrak
- source URL
- downloaded date

If the export does not include every field, keep what is available. The script can still use package name, institution, budget similarity, and year similarity.

## Prioritizing May/June 2026 Packages

Start with packages from SiRUP where `pemilihan` or `idBulan` indicates May 2026 or June 2026.

Recommended order:

1. High budget packages
2. Medical device / healthcare equipment packages
3. Packages with specific product names such as cathlab, analyzer, USG, radiology, ICU, BMHP, alat kesehatan, or peralatan kesehatan
4. Packages from hospitals, health agencies, RSUD, Puskesmas, and Ministry of Health work units
5. Packages where SiRUP method is tender, non-tender, e-purchasing, or pengadaan langsung

For each priority package, manually search SPSE Nasional and the relevant LPSE/Katalog source. Save any public result page or export that shows process, winner, contract, completion, cancellation, or no-match context.

## Running the Crosscheck Script

Default run:

```powershell
python scripts\crosscheck_sirup_procurement_status.py
```

Run for May 2026:

```powershell
python scripts\crosscheck_sirup_procurement_status.py --month 5 --limit 1000
```

Run for June 2026:

```powershell
python scripts\crosscheck_sirup_procurement_status.py --month 6 --limit 1000
```

Run with explicit evidence files:

```powershell
python scripts\crosscheck_sirup_procurement_status.py --evidence-files data\evidence\spse\20260705_spse_nasional_tender_alkes_may_june_2026.xlsx data\evidence\winners\20260705_winners_rsud_cathlab_2026.csv
```

Run with a keyword filter:

```powershell
python scripts\crosscheck_sirup_procurement_status.py --keyword "alat kesehatan|alkes|cathlab|analyzer|usg|radiologi" --limit 1000
```

Run with generic-content scanning if evidence files have generic names:

```powershell
python scripts\crosscheck_sirup_procurement_status.py --scan-generic-content --limit 1000
```

Output workbook:

`outputs/sirup_procurement_status_crosscheck.xlsx`

## Interpreting Status Safely

The script uses factual status categories only:

- `PLANNING_ONLY_SIRUP`: no matching local evidence was found. This does not mean the package is still open or not purchased.
- `FOUND_TENDER_PROCESS`: local evidence shows a tender process exists.
- `FOUND_NON_TENDER_PROCESS`: local evidence shows a non-tender or pengadaan langsung process exists.
- `FOUND_E_PURCHASING_PROCESS`: local evidence shows e-purchasing or katalog evidence exists.
- `FOUND_WINNER`: local evidence shows pemenang exists.
- `FOUND_CONTRACT`: local evidence shows contract, berkontrak, or tanda tangan kontrak evidence exists.
- `FOUND_COMPLETED`: local evidence shows selesai/completed status.
- `FOUND_CANCELLED_OR_FAILED`: local evidence shows batal, dibatalkan, or gagal.
- `NEEDS_MANUAL_CHECK`: matching evidence is ambiguous and needs human review.

Every non-planning status should have source type, evidence file, reference or URL if available, matched text, match basis, and confidence reason.

## Manual Review Notes

When reviewing results, prefer official source evidence over copied summaries. Keep notes factual:

- Good: `LPSE saved page shows pemenang for package name with matching budget and institution.`
- Good: `SPSE export contains tender ID and package name matching RUP package.`
- Avoid: `Probably already purchased.`
- Avoid: `Still open because only SiRUP exists.`

SiRUP is the plan. SPSE/LPSE/e-purchasing/contract/winner evidence is what moves a row beyond planning.
