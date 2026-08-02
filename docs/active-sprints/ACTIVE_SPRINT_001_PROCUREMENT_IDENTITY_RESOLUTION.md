# NOVANUSA â€” ACTIVE SPRINT 1

## PROCUREMENT IDENTITY RESOLUTION FOUNDATION

**Status:** LOCKED CONTRACT â€” siap untuk Codex
**Predecessor:** Sprint 0 (Verdict: BLOCKED â€” lihat blocking reason di bawah)
**Positioning acuan:** NovaNusa = AI Procurement \& Sales Operating System, Canonical Domain Authority, seluruh business state hanya berubah melalui **Domain API**.

\---



## Governing Addendum

This Sprint contract is governed by:

docs/governance/NOVANUSA\_SPRINT1\_GOVERNANCE\_ADDENDUM.md

Rules 1–8 are defined in this Active Sprint.
Rules 9–10 are defined in the Governance Addendum.
Both documents are mandatory and together form the complete Sprint 1 contract.

For conflict classification and severity only, Governance Addendum Rule 9
explicitly amends and supersedes any conflicting classification in Rule 3.
Rule 3 continues to govern rejection timing and requires rejection before
ranking only for conflicts classified as HARD under Rule 9.

## 1\. Objective

Membangun pipeline deterministic untuk mencocokkan satu record SiRUP dengan evidence SPSE/LPSE/e-purchasing yang benar-benar sama secara identitas, **sebelum** factual procurement status atau opportunity qualification ditetapkan.

Sprint ini TIDAK bertujuan menghasilkan lebih banyak match. Sprint ini bertujuan menghasilkan match yang **benar**, termasuk secara eksplisit menghasilkan lebih sedikit match jika itu artinya menghilangkan false positive.

Blocking reason dari Sprint 0 yang harus diselesaikan sprint ini:

```text
Procurement identity matching menghasilkan false positive dan belum dapat
dipercaya sebagai dasar factual procurement status maupun opportunity
qualification.
```

\---

## 2\. Locked Rules (Matching Contract)

### Rule 1 â€” Identifier Namespace Separation

```text
RUP ID â‰  SiRUP id\\\_referensi â‰  SPSE package code â‰  LPSE package code
```

Tidak ada dua identifier dari namespace berbeda yang boleh dianggap "sama" hanya karena nilainya cocok secara numerik. Kesetaraan lintas-namespace hanya boleh dipakai jika sudah didokumentasikan sebagai known cross-system relation.

### Rule 2 â€” No Single-Signal Acceptance

Satu exact-ID match TIDAK PERNAH cukup untuk diterima sebagai identitas yang sama. Minimal dua sinyal independen diperlukan, dan salah satunya wajib salah satu dari:

* package name similarity
* institution/satker match

### Rule 3 â€” Hard Conflict Rejection

Kandidat WAJIB ditolak (bukan diberi skor rendah â€” ditolak) jika ditemukan
konflik yang diklasifikasikan sebagai HARD oleh Governance Addendum Rule 9:

* institution conflict
* satker conflict
* completely different package
* major procurement-method conflict

Year conflict and minor procurement-method difference are SOFT conflicts under
Rule 9 and do not independently require rejection.

Conflict rejection dijalankan SEBELUM ranking, bukan sebagai bagian dari scoring gabungan.

### Rule 4 â€” Identity Before Status (urutan wajib, tidak boleh dibalik)

```text
discover\\\_candidates()
  â†’ score\\\_identity()
  â†’ reject\\\_conflicts()
  â†’ rank\\\_candidates()
  â†’ confirm\\\_or\\\_manual\\\_review()
  â†’ extract\\\_procurement\\\_status()
```

### Rule 5 â€” Status Must Not Rank Identity

`STATUS\\\_PRIORITY` (atau struktur sejenis) DILARANG digunakan untuk memilih kandidat identitas. Status procurement hanya boleh dipakai SETELAH canonical identity ditetapkan â€” misalnya untuk memilih evidence terbaru dari paket yang identitasnya sudah dikonfirmasi sama.

### Rule 6 â€” Separate Result Objects

Tiga jenis hasil harus dipisah sebagai objek berbeda, tidak boleh dicampur dalam satu struct:

**Identity result:**

```text
identity\\\_status
identity\\\_confidence
candidate\\\_list
match\\\_signals
conflicts
manual\\\_review\\\_required
```

**Evidence result:**

```text
evidence\\\_type
source\\\_url
source\\\_file
collected\\\_at
provenance
```

**Procurement result:**

```text
source\\\_status
normalized\\\_status
observed\\\_at
status\\\_evidence
```

\---

## 3\. In Scope

* Pisahkan identity resolution dari procurement status secara struktural (kode dan data model)
* Hapus exact-code shortcut lintas namespace (`exact\\\_match` yang menyamakan `rup\\\_id`/`package\\\_id` langsung dengan `spse\\\_package\\\_code`)
* Hapus `STATUS\\\_PRIORITY` dari candidate ranking di `crosscheck\\\_sirup\\\_procurement\\\_status.py`
* Tambahkan hard-conflict rejection (Rule 3) sebagai tahap eksplisit sebelum ranking
* Tambahkan minimum corroborating signal requirement (Rule 2)
* Output candidate list, identity confidence, dan manual review reason untuk setiap record
* Pertahankan seluruh evidence file lama sebagai *candidate evidence* â€” jangan dihapus, jangan dianggap valid otomatis
* Regression tests untuk seluruh false-positive case yang sudah ditemukan (lihat Section 5)
* Re-run sample dataset (bukan full national dataset) dan bandingkan distribusi hasil lama vs baru

## 4\. Out of Scope

Dilarang dikerjakan pada sprint ini, terlepas dari seberapa mudah kelihatannya:

* Dashboard redesign
* Migrasi database besar / full production database
* OpenClaw
* Telegram
* Hermes
* AI scoring / predictive scoring dalam bentuk apa pun
* Browser automation
* Full national recrawl SPSE/LPSE
* Sales outreach automation
* Deployment production

Jika Codex menemukan kebutuhan untuk menyentuh salah satu area di atas agar sprint ini berhasil, itu harus dilaporkan sebagai **finding**, bukan dikerjakan langsung.

\---

## 5\. Mandatory Regression Test Cases

Semua enam kasus berikut WAJIB lulus sebelum sprint dianggap selesai. Ini bukan "nice to have" â€” ini adalah kontrak minimum.

|#|Skenario|Input|Expected Result|
|-|-|-|-|
|1|Same `package\\\_id`, different package|SiRUP: "Pembangunan Jalan KSPEAN Wanam - Muting Segmen I" vs Evidence: "Pengadaan Barrier Gate dan Alat Kamera"|`REJECTED\\\_IDENTITY\\\_CONFLICT`|
|2|Same `package\\\_id`, different institution|â€”|`REJECTED\\\_INSTITUTION\\\_CONFLICT`|
|3|Same numeric RUP ID and SPSE code, no corroboration|Tidak ada nama paket/institusi yang cocok|`NEEDS\\\_MANUAL\\\_REVIEW` atau `NO\\\_MATCH` â€” **tidak boleh** `exact`|
|4|Strong name + institution + year + close budget|Multi-signal match kuat|`PROBABLE\\\_MATCH` atau `CONFIRMED\\\_MATCH` sesuai threshold kontrak|
|5|Strong identity, multiple status evidence|Identity sudah confirmed, ada beberapa evidence status|Identity ditetapkan lebih dulu; status terbaru dipilih HANYA dari evidence milik identity yang sama|
|6|No evidence found|â€”|`SIRUP\\\_PLANNING\\\_ONLY` â€” dengan makna eksplisit: tidak ada evidence lokal ditemukan, BUKAN bukti bahwa pengadaan belum berjalan|

\---

## 6\. Required Files to Inspect / Modify

```text
scripts/crosscheck\\\_sirup\\\_procurement\\\_status.py   â† core fix (Rule 4, Rule 5)
scripts/map\\\_sirup\\\_to\\\_spse\\\_evidence.py            â† core fix (Rule 1, Rule 2, Rule 3)
outputs/evidence/sirup\\\_spse\\\_evidence\\\_mapping.xlsx        â† evidence lama, jangan dihapus
outputs/sirup\\\_procurement\\\_status\\\_crosscheck.xlsx         â† evidence lama, jangan dihapus
```

Baseline lama harus dipertahankan sebagai arsip pembanding (lihat Section 8), bukan ditimpa.

\---

## 7\. Implementation Constraints

1. Tidak mengubah arsitektur, domain, workflow, atau capability map NovaNusa â€” sprint ini murni perbaikan logic matching.
2. Tidak menambahkan dependency baru tanpa alasan eksplisit yang dilaporkan.
3. Tidak melakukan full recrawl SPSE/LPSE â€” bekerja dari evidence file yang sudah ada.
4. Setiap perubahan pada scoring/threshold harus disertai penjelasan tertulis kenapa angka itu dipilih (tidak boleh angka arbitrer tanpa dokumentasi).
5. Kode baru untuk identity resolution harus dapat diuji secara terisolasi dari kode procurement-status â€” sejalan dengan Rule 6 (separate result objects).

\---

## 8\. Baseline Preservation (wajib dijalankan sebelum Codex mengubah kode apa pun)

```powershell
cd D:\\\\AI\\\_WORKSPACE\\\\novanusa

Write-Host "===== BASELINE ====="
git branch --show-current
git rev-parse HEAD
git status --short
git log -1 --oneline
```

```powershell
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"

New-Item -ItemType Directory `
  -Path ".\\\\outputs\\\\audit\\\\pre-identity-fix-$Stamp" `
  -Force | Out-Null

Copy-Item ".\\\\outputs\\\\sirup\\\_procurement\\\_status\\\_crosscheck.xlsx" `
  ".\\\\outputs\\\\audit\\\\pre-identity-fix-$Stamp\\\\" -ErrorAction SilentlyContinue

Copy-Item ".\\\\outputs\\\\evidence\\\\sirup\\\_spse\\\_evidence\\\_mapping.xlsx" `
  ".\\\\outputs\\\\audit\\\\pre-identity-fix-$Stamp\\\\" -ErrorAction SilentlyContinue

Copy-Item ".\\\\outputs\\\\evidence\\\\sirup\\\_spse\\\_evidence\\\_mapping\\\_summary.json" `
  ".\\\\outputs\\\\audit\\\\pre-identity-fix-$Stamp\\\\" -ErrorAction SilentlyContinue
```

\---

## 9\. Quality Gates (semua wajib PASS)

```text
\\\[ ] Baseline preserved (git state + output backup)
\\\[ ] exact\\\_match() cross-namespace shortcut dihapus
\\\[ ] STATUS\\\_PRIORITY dihapus dari candidate ranking
\\\[ ] Hard conflict rejection diimplementasikan sebagai tahap terpisah
\\\[ ] Minimum corroborating signal diimplementasikan
\\\[ ] Identity result, Evidence result, Procurement result adalah struct/object terpisah
\\\[ ] Seluruh 6 regression test case (Section 5) PASS
\\\[ ] Sample dataset re-run selesai, distribusi lama vs baru dibandingkan dan didokumentasikan
\\\[ ] Tidak ada perubahan di luar In Scope (Section 3)
```

\---

## 10\. Definition of Done

Sprint 1 dianggap selesai HANYA jika:

1. Semua Quality Gates di Section 9 PASS.
2. Distribusi hasil matching baru menunjukkan penurunan match count dibanding baseline lama (848/1000) â€” ini **diharapkan dan benar**, bukan tanda kegagalan. Jumlah match yang lebih sedikit tapi valid lebih baik daripada jumlah besar yang mengandung false positive.
3. Setiap keputusan REJECTED / NEEDS\_MANUAL\_REVIEW / CONFIRMED\_MATCH pada sample dataset dapat ditelusuri ke sinyal spesifik yang menghasilkannya (evidence-based, sesuai prinsip Evidence-Based Only).
4. Tidak ada perubahan pada domain lain di luar Procurement Identity Resolution.
5. Completion Report (Section 11) sudah diserahkan.

\---

## 11\. Completion Report Format

```text
1  Executive Summary
2  Baseline Preservation Confirmation (commit hash, backup path)
3  Code Changes Summary (file, before/after logic)
4  Regression Test Results (6 kasus wajib, per-kasus PASS/FAIL)
5  Sample Dataset Re-run Results
   - old match distribution
   - new match distribution
   - delta explanation
6  Rejected/Manual-Review Case Examples (minimal 3 contoh nyata dari sample)
7  Deviations from Contract (jika ada, dengan justifikasi)
8  Risks / Observations
9  Recommendation for Sprint 2
10 Final Verdict (PASS / BLOCKED, dengan alasan jika BLOCKED)
```

\---

## 12\. Explicit Prohibitions for This Sprint

```text
Sprint 1 dilarang:
- mengubah arsitektur NovaNusa
- mengubah domain atau capability map
- menambahkan AI/agent automation (OpenClaw, Hermes, Telegram)
- melakukan full national recrawl
- mempercayai angka 848/1000 dari hasil lama sebagai valid
- menghapus evidence file lama (harus diarsipkan, bukan dihapus)
```
