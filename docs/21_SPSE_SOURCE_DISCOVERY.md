# 21. SPSE National Source Discovery & API Analysis

Dokumen ini merangkum discovery teknis atas portal SPSE Nasional untuk memahami cara data publik disajikan, dengan batasan ketat: discovery kecil, public-only, tanpa crawling massal, tanpa bypass proteksi, dan tanpa akses ke endpoint yang membutuhkan autentikasi yang tidak tersedia.

Discovery ini berdasarkan sampel halaman dan raw evidence yang sudah tersimpan di repo pada 2026-07-05, terutama HTML halaman SPSE Nasional dan response DataTables yang berhasil ditangkap untuk `tender`, `nontender`, dan `darurat`.

## 1. Ringkasan

SPSE Nasional menyajikan daftar paket melalui halaman HTML publik yang memakai JavaScript, Bootstrap, dan DataTables. Tabel paket diisi lewat request AJAX POST ke endpoint server-side DataTables di bawah path `/nasional/dt/`.

Temuan utama:
- Halaman daftar paket memakai DataTables server-side.
- Request tabel mengirim parameter DataTables standar plus `tahun` dan `authenticityToken`.
- HTML memuat token anti-CSRF yang digunakan sebagai field POST.
- Tersedia tiga sumber utama: `tender`, `nontender`, dan `darurat`.
- Response publik yang berhasil diamati berbentuk JSON DataTables dengan keys `draw`, `recordsTotal`, `recordsFiltered`, dan `data`.
- Identifier paket yang paling stabil untuk evidence adalah `package_code` dari row tabel.

Pembatasan penting:
- Browser automation pada environment ini sempat menerima halaman challenge / HTTP 403 saat mencoba memuat portal secara langsung.
- Tidak ada discovery yang mengandalkan bypass proteksi.
- Tidak ditemukan bukti kebutuhan GraphQL, XML, atau CSV publik untuk daftar paket.

## 2. Struktur Portal

### Halaman yang dianalisis

- `https://spse.inaproc.id/nasional/lelang`
- `https://spse.inaproc.id/nasional/nontender`
- `https://spse.inaproc.id/nasional/darurat`
- `https://spse.inaproc.id/`

### Pola HTML

Setiap halaman daftar memiliki pola berikut:
- header portal SPSE Nasional
- tab navigasi antar jenis paket
- form filter publik
- tabel daftar paket dengan id tabel utama `tbllelang`
- script inisialisasi DataTables

### JavaScript yang terdeteksi

Library dan skrip yang terlihat di raw HTML:
- jQuery 3.7.1
- Bootstrap 4.6.2
- DataTables 1.13.5
- DataTables Bootstrap 4 integration
- moment.js 2.29.4
- bootstrap-select
- bootstrap-datetimepicker
- bootstrap-dialog
- jquery.cookie
- jquery.maskedinput
- jquery.webticker
- skrip lokal seperti `datatables-v1.config.js`, `datatable-handler.js`, `common-v2.js`, dan `message-constants.js`

### DataTables atau bukan

Ya. Daftar paket dimuat sebagai DataTables server-side.

### AJAX atau bukan

Ya. Tabel tidak diisi dari HTML statis saja, tetapi melalui AJAX POST ke endpoint DataTables di server.

## 3. Struktur Network

### Endpoint publik yang ditemukan

Discovery menemukan endpoint publik berikut:

- halaman daftar:
  - `GET /nasional/lelang?tahun=YYYY`
  - `GET /nasional/nontender?tahun=YYYY`
  - `GET /nasional/darurat?tahun=YYYY`
- DataTables data source:
  - `POST /nasional/dt/lelang?tahun=YYYY`
  - `POST /nasional/dt/pl?tahun=YYYY`
  - `POST /nasional/dt/darurat-list?tahun=YYYY`
- detail record:
  - `GET /nasional/lelang/{id}/pengumumanlelang`
  - `GET /nasional/lelang/{id}/jadwal`
  - `GET /nasional/nontender/{id}/pengumumanpl`
  - `GET /nasional/nontender/{id}/jadwal`
  - `GET /nasional/darurat/pengumumandarurat?id={id}`

### Bentuk request yang terlihat

Request tabel memakai:
- `POST`
- `Content-Type` form submission biasa
- field `authenticityToken`
- parameter DataTables standar seperti `draw`, `start`, `length`, `search`, dan `order`
- filter `tahun`

### Format response

- daftar paket: JSON
- detail halaman: HTML

Tidak ditemukan bukti endpoint publik GraphQL, XML, atau export CSV langsung pada sampel ini.

## 4. Endpoint Publik yang Ditemukan

| Endpoint | Method | Public | Auth required | Response | Catatan |
|---|---:|---:|---:|---|---|
| `/nasional/lelang?tahun=YYYY` | GET | true | false | HTML | Halaman publik tender |
| `/nasional/nontender?tahun=YYYY` | GET | true | false | HTML | Halaman publik non tender |
| `/nasional/darurat?tahun=YYYY` | GET | true | false | HTML | Halaman publik darurat |
| `/nasional/dt/lelang?tahun=YYYY` | POST | true | false | JSON DataTables | Server-side table source |
| `/nasional/dt/pl?tahun=YYYY` | POST | true | false | JSON DataTables | Server-side table source |
| `/nasional/dt/darurat-list?tahun=YYYY` | POST | true | false | JSON DataTables | Server-side table source |
| `/nasional/lelang/{id}/pengumumanlelang` | GET | true | false | HTML | Detail pengumuman tender |
| `/nasional/lelang/{id}/jadwal` | GET | true | false | HTML | Detail jadwal tender |
| `/nasional/nontender/{id}/pengumumanpl` | GET | true | false | HTML | Detail pengumuman non tender |
| `/nasional/nontender/{id}/jadwal` | GET | true | false | HTML | Detail jadwal non tender |
| `/nasional/darurat/pengumumandarurat?id={id}` | GET | true | false | HTML | Detail pengumuman darurat |

## 5. Parameter

### Parameter publik yang teramati

Filter halaman:
- `tahun`
- `kategoriId`
- `instansiId`
- `rekanan`
- `kontrak_status` pada tender
- `kontrak_tipe` pada tender

Parameter DataTables standar:
- `draw`
- `start`
- `length`
- `search[value]`
- `search[regex]`
- `order[0][column]`
- `order[0][dir]`
- `columns[i][data]`
- `columns[i][name]`
- `columns[i][searchable]`
- `columns[i][orderable]`
- `columns[i][search][value]`
- `columns[i][search][regex]`

Parameter tambahan:
- `authenticityToken`

### Catatan parameter

`tahun` paling penting untuk collector karena mengunci volume data dan mencegah crawling massal.

`kategoriId`, `instansiId`, dan `rekanan` tampak sebagai filter UI publik, tetapi discovery ini belum membuktikan seluruh kombinasi nilainya pada semua endpoint.

## 6. Response Schema

### Schema DataTables umum

Response JSON yang diamati memiliki struktur:

- `draw`: integer
- `recordsTotal`: integer
- `recordsFiltered`: integer
- `data`: array of rows

### Schema row tender

Row tender diamati sebagai array terurut dengan sekitar 16 elemen. Field yang dapat diturunkan dari sampel:
- `package_code`
- `package_name`
- `institution_name`
- `stage_or_status`
- `hps_or_pagu`
- `procurement_method`
- `source_type`
- `procurement_category_or_work_type`
- `participant_count_or_related_counter`
- `contract_state_or_note`

### Schema row non tender

Row non tender diamati sebagai array terurut dengan sekitar 12 elemen. Field utama yang terlihat:
- `package_code`
- `package_name`
- `institution_name`
- `stage_or_status`
- `hps_or_pagu`
- `procurement_method`
- `source_type`
- `work_type_or_category`
- `fiscal_year`
- `contract_state_or_note`

### Schema row darurat

Row darurat diamati sebagai array terurut dengan sekitar 8 elemen. Field utama:
- `package_code`
- `package_name`
- `institution_name`
- `hps_or_pagu`
- `fiscal_year`
- `stage_or_status`
- `work_type`

### Contoh hubungan antar field

- `package_code` identitas paket
- `package_name` nama paket yang dipakai untuk matching fuzzy
- `institution_name` pemilah penting untuk disambiguasi
- `hps_or_pagu` dipakai sebagai sinyal konsistensi nilai
- `stage_or_status` mengindikasikan progres paket

## 7. Pagination

### Pola pagination

DataTables memakai pagination berbasis:
- `start`
- `length`

### Page size

Page size dapat diubah melalui request DataTables jika UI mengizinkan. Bukti pasti tentang seluruh opsi page size belum diambil, tetapi parameter `length` jelas diterima oleh endpoint tabel.

### Total records

Response yang diamati pada sampel menggunakan nilai total yang tidak realistis untuk jumlah data nyata, sehingga `recordsTotal` dan `recordsFiltered` tidak layak dipakai sebagai angka populasi final tanpa verifikasi tambahan.

### Implikasi collector

Collector sebaiknya:
- gunakan `tahun`
- gunakan `length` kecil untuk sample
- jangan mengandalkan total records sebagai ground truth

## 8. Identifier

### Identifier yang stabil

Identifier paling layak sebagai Primary Evidence Identifier:
- `package_code`

Identifier lain:
- `id` pada detail URL record
- `tahun`
- `source_type`
- `institution_name`

### Penilaian

`package_code` adalah pilihan terbaik karena muncul langsung di row tabel dan paling cocok untuk provenance evidence.

`id` detail URL berguna untuk drill-down, tetapi bukan selalu representasi yang paling portable lintas konteks.

`instansiId` dan `kategoriId` adalah identifier filter, bukan identifier paket.

## 9. Relasi LPSE

Discovery ini menunjukkan bahwa record berada di portal SPSE Nasional, tetapi relasi eksplisit ke LPSE asal tidak selalu muncul langsung pada row tabel sampel.

Yang tersedia:
- nama instansi
- detail halaman paket
- navigasi ke halaman pengumuman dan jadwal

Yang belum tervalidasi pada sampel kecil ini:
- URL LPSE asal per record
- `lpse_id` yang eksplisit pada row publik
- relasi langsung ke katalog LPSE daerah secara konsisten

Kesimpulan teknis:
- hubungan ke LPSE atau sumber detail kemungkinan ada di halaman detail, bukan selalu di row tabel utama
- collector berikutnya perlu melakukan drill-down ringan hanya untuk record yang sudah dipilih sebagai evidence

## 10. Kualitas Data

### Data yang tersedia

Terlihat tersedia:
- nama paket
- instansi
- HPS atau pagu
- metode
- status atau tahap
- tahun

### Data yang tidak selalu tersedia atau belum tervalidasi

- pemenang
- kontrak
- jadwal lengkap
- detail tahapan terstruktur
- relasi LPSE asal

### Catatan kualitas

Beberapa field pada row tabel berupa label atau status ringkas, bukan schema terstruktur penuh. Ini cukup untuk evidence awal, tetapi bukan cukup untuk analitik lanjutan tanpa kunjungan ke halaman detail.

## 11. Keterbatasan

- Environment browser pada discovery ini sempat menerima halaman challenge / 403.
- Tidak ada bukti bahwa endpoint publik yang dianalisis memerlukan login, tetapi proteksi perimeter tetap terlihat.
- Discovery ini tidak melakukan bypass proteksi.
- Discovery ini tidak melakukan crawling massal.
- Nilai total di DataTables response tidak bisa dipercaya sebagai total record final tanpa validasi tambahan.
- Schema row bersifat array, jadi mapping field harus dijaga per source type.

## 12. Rekomendasi Arsitektur Collector NovaNusa

1. Ambil halaman HTML kecil per source type dan simpan raw HTML.
2. Ekstrak `authenticityToken`, URL DataTables, dan filter `tahun`.
3. Kirim request POST kecil ke endpoint DataTables dengan `length` rendah.
4. Simpan response JSON mentah sebagai evidence raw.
5. Parse row array ke schema terstandar per source type.
6. Gunakan `package_code` sebagai primary evidence identifier.
7. Simpan provenance lengkap:
   - `source_url`
   - `source_type`
   - `collected_at`
   - `raw_file_path`
   - `evidence_level`
8. Untuk record kandidat yang penting, lakukan drill-down ke detail halaman dengan jumlah sangat kecil.

Rekomendasi praktis:
- pertahankan collector kecil
- jangan gunakan score prediktif
- treat SPSE sebagai evidence layer, bukan opportunity engine

### Referensi file evidence lokal

- `data/evidence/spse/nasional/raw/2026-07-05T200900Z0000_tender_2026.html`
- `data/evidence/spse/nasional/raw/2026-07-05T200900Z0000_tender_2026_datatable.json`
- `data/evidence/spse/nasional/raw/2026-07-05T200900Z0000_nontender_2026.html`
- `data/evidence/spse/nasional/raw/2026-07-05T200900Z0000_nontender_2026_datatable.json`
- `data/evidence/spse/nasional/raw/2026-07-05T200900Z0000_darurat_2026.html`
- `data/evidence/spse/nasional/raw/2026-07-05T200900Z0000_darurat_2026_datatable.json`

