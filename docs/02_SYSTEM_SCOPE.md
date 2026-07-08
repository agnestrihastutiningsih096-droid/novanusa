# 02 — NOVANUSA SYSTEM SCOPE

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan resmi mengenai ruang lingkup sistem NovaNusa.

Dokumen ini menetapkan batasan, cakupan, domain, aktor, kapabilitas, dan hal-hal yang tidak termasuk dalam ruang lingkup awal platform.

Seluruh keputusan implementasi wajib mengikuti ruang lingkup yang ditetapkan dalam dokumen ini.

---

# Tujuan Dokumen

Dokumen ini bertujuan untuk memastikan bahwa pengembangan NovaNusa berjalan fokus, terarah, dan tidak melebar di luar tujuan utama platform.

Dokumen ini menjelaskan:

- apa saja yang termasuk dalam ruang lingkup NovaNusa;
- apa saja yang tidak termasuk dalam ruang lingkup NovaNusa;
- batas tanggung jawab sistem;
- aktor utama yang dilayani;
- domain bisnis yang menjadi fokus;
- kapabilitas inti platform;
- batas penggunaan AI;
- batas integrasi eksternal;
- prinsip ekspansi sistem di masa depan.

Dokumen ini menjadi rujukan utama untuk mencegah scope creep.

---

# Definisi Ruang Lingkup

Ruang lingkup NovaNusa adalah seluruh proses yang berkaitan dengan pengumpulan, pengolahan, pemahaman, analisis, pencocokan, dan penyajian informasi peluang kebutuhan institusi pemerintah Indonesia.

NovaNusa berfokus pada intelligence.

Bukan transaksi.

Bukan sistem pengadaan resmi.

Bukan sistem pengganti e-Katalog, SiRUP, LPSE, atau sistem pemerintah lainnya.

NovaNusa adalah platform pendukung analisis dan keputusan bisnis berbasis data publik dan knowledge internal.

---

# Fokus Utama Sistem

Fokus utama NovaNusa adalah:

> Mengubah data kebutuhan pemerintah menjadi knowledge, insight, rekomendasi peluang, dan dasar tindakan bisnis yang dapat diverifikasi.

Dengan demikian NovaNusa harus selalu berfokus pada:

- data pemerintah;
- kebutuhan institusi;
- peluang pengadaan;
- produk;
- principal;
- pencocokan kebutuhan dengan solusi;
- prioritas bisnis;
- insight strategis;
- decision support.

---

# Ruang Lingkup Inti

Ruang lingkup inti NovaNusa terdiri dari delapan area utama.

---

## 1. Data Acquisition

NovaNusa mencakup proses pengambilan data dari sumber-sumber yang relevan.

Sumber data dapat meliputi:

- SiRUP;
- e-Katalog;
- LPSE;
- website institusi pemerintah;
- dokumen publik;
- data principal;
- data produk;
- data kontak institusi;
- data internal yang disediakan pengguna.

Data acquisition bertujuan menyediakan bahan mentah untuk proses intelligence.

---

## 2. Data Cleaning

NovaNusa mencakup proses pembersihan data agar informasi dapat digunakan secara konsisten.

Pembersihan data dapat meliputi:

- menghapus duplikasi;
- memperbaiki format teks;
- menstandarkan nama institusi;
- menstandarkan wilayah;
- menstandarkan kategori;
- mendeteksi data kosong;
- mendeteksi data tidak valid;
- memisahkan data relevan dan tidak relevan.

Data yang buruk tidak boleh langsung menjadi dasar rekomendasi.

---

## 3. Data Normalization

NovaNusa mencakup proses normalisasi data agar entitas yang sama dapat dikenali sebagai satu identitas.

Contoh normalisasi:

- “Dinas Pendidikan”
- “DINAS PENDIDIKAN”
- “Dinas Pendidikan Kab. Sleman”
- “Dinas Pendidikan Kabupaten Sleman”

Sistem harus mampu membedakan mana yang sama, mana yang berbeda, dan mana yang perlu ditinjau ulang.

Normalisasi merupakan dasar penting untuk membangun single source of truth.

---

## 4. Knowledge Building

NovaNusa mencakup proses pembangunan knowledge dari data yang telah dibersihkan dan dinormalisasi.

Knowledge dapat berupa hubungan antara:

- institusi dan wilayah;
- institusi dan sektor;
- institusi dan histori kebutuhan;
- paket dan kategori;
- kategori dan produk;
- produk dan principal;
- principal dan portofolio;
- peluang dan strategi tindak lanjut.

Knowledge adalah aset utama sistem.

---

## 5. Opportunity Detection

NovaNusa mencakup proses identifikasi peluang dari data pemerintah.

Peluang dapat berasal dari:

- paket pengadaan yang sedang direncanakan;
- kebutuhan yang berulang;
- anggaran yang meningkat;
- pola pengadaan historis;
- indikasi kebutuhan baru;
- tren sektor tertentu;
- kecocokan antara kebutuhan dan produk.

Opportunity detection harus selalu memiliki dasar data yang jelas.

---

## 6. Product Matching

NovaNusa mencakup proses pencocokan antara kebutuhan institusi dengan produk atau solusi yang tersedia.

Pencocokan dapat mempertimbangkan:

- kata kunci kebutuhan;
- kategori produk;
- fungsi produk;
- spesifikasi produk;
- merek;
- principal;
- kesesuaian sektor;
- relevansi historis;
- tingkat keyakinan.

Product matching tidak boleh hanya bergantung pada pencocokan kata secara literal.

---

## 7. Intelligence Dashboard

NovaNusa mencakup penyajian informasi melalui dashboard analitik.

Dashboard harus membantu pengguna memahami:

- peluang prioritas;
- institusi potensial;
- kategori kebutuhan;
- distribusi wilayah;
- distribusi anggaran;
- principal relevan;
- tren pengadaan;
- status tindak lanjut;
- rekomendasi tindakan.

Dashboard bukan sekadar tabel.

Dashboard harus menjadi alat pengambilan keputusan.

---

## 8. AI-Assisted Analysis

NovaNusa mencakup penggunaan AI untuk membantu proses analisis.

AI dapat digunakan untuk:

- klasifikasi;
- ekstraksi informasi;
- pencocokan semantik;
- penyusunan ringkasan;
- penyusunan rekomendasi;
- penjelasan hasil analisis;
- interaksi berbasis bahasa alami.

AI harus mendukung sistem, bukan menggantikan validasi manusia.

---

# Ruang Lingkup Bisnis

NovaNusa berada dalam ruang lingkup bisnis procurement intelligence.

Platform ini membantu pihak penyedia memahami kebutuhan institusi pemerintah berdasarkan data yang tersedia.

Ruang lingkup bisnis mencakup:

- identifikasi peluang;
- prioritisasi prospek;
- pemetaan kebutuhan;
- pemetaan institusi;
- pemetaan produk;
- pemetaan principal;
- analisis pasar pemerintah;
- pendukung strategi sales;
- pendukung strategi distribusi;
- pendukung strategi principal.

NovaNusa tidak menjalankan proses transaksi pengadaan.

NovaNusa hanya membantu analisis dan pengambilan keputusan sebelum tindakan bisnis dilakukan.

---

# Aktor Utama Sistem

NovaNusa dirancang untuk melayani beberapa aktor utama.

---

## 1. Administrator

Administrator bertanggung jawab menjaga kualitas sistem.

Administrator dapat mengelola:

- konfigurasi sistem;
- data master;
- kategori;
- user;
- hak akses;
- validasi data;
- quality control.

Administrator memastikan sistem tetap stabil dan konsisten.

---

## 2. Analis

Analis menggunakan NovaNusa untuk memahami data dan menghasilkan insight.

Analis dapat melakukan:

- eksplorasi data;
- validasi peluang;
- evaluasi hasil matching;
- analisis tren;
- investigasi institusi;
- penyusunan rekomendasi strategis.

Analis membutuhkan akses detail dan kemampuan drill-down.

---

## 3. Tim Sales

Tim sales menggunakan NovaNusa untuk menentukan prospek prioritas.

Tim sales membutuhkan informasi seperti:

- institusi yang perlu dihubungi;
- kebutuhan utama;
- produk yang sesuai;
- tingkat prioritas;
- kontak yang tersedia;
- alasan rekomendasi;
- status tindak lanjut.

NovaNusa membantu sales bekerja lebih terarah.

---

## 4. Manajemen

Manajemen menggunakan NovaNusa untuk melihat gambaran besar.

Manajemen membutuhkan:

- ringkasan peluang;
- kategori potensial;
- wilayah prioritas;
- tren anggaran;
- performa pipeline;
- potensi principal;
- keputusan strategis.

Manajemen tidak membutuhkan detail operasional sebanyak analis, tetapi membutuhkan insight yang kuat.

---

## 5. Principal

Principal dapat menggunakan NovaNusa untuk memahami pasar pemerintah yang relevan dengan produknya.

Principal membutuhkan:

- sektor yang cocok;
- wilayah dengan permintaan tinggi;
- institusi potensial;
- produk paling relevan;
- kategori yang sedang tumbuh;
- peluang kolaborasi.

Akses principal dapat dibatasi sesuai kebutuhan bisnis.

---

# Domain Sistem

NovaNusa memiliki beberapa domain utama yang menjadi batas kerja platform.

---

## Domain Institusi

Domain institusi mencakup seluruh data terkait organisasi pemerintah.

Termasuk:

- nama institusi;
- jenis institusi;
- sektor;
- wilayah;
- level pemerintahan;
- histori pengadaan;
- pola kebutuhan;
- kontak publik;
- relasi antar institusi.

Domain ini menjadi pusat analisis permintaan.

---

## Domain Pengadaan

Domain pengadaan mencakup data kebutuhan dan paket pengadaan.

Termasuk:

- nama paket;
- tahun anggaran;
- pagu;
- metode pengadaan;
- sumber data;
- kategori kebutuhan;
- status;
- satuan kerja;
- lokasi;
- metadata relevan.

Domain ini menjadi sumber utama opportunity detection.

---

## Domain Produk

Domain produk mencakup seluruh informasi mengenai barang atau solusi yang dapat ditawarkan.

Termasuk:

- nama produk;
- kategori;
- merek;
- principal;
- fungsi;
- spesifikasi;
- kata kunci;
- produk substitusi;
- produk pelengkap;
- relevansi sektor.

Domain ini menjadi dasar product matching.

---

## Domain Principal

Domain principal mencakup perusahaan pemilik merek, produsen, distributor utama, atau penyedia solusi.

Termasuk:

- nama principal;
- portofolio produk;
- kategori;
- sektor sasaran;
- cakupan wilayah;
- hubungan dengan produk;
- hubungan dengan distributor;
- status kerja sama.

Domain ini menjadi dasar strategi kemitraan.

---

## Domain Opportunity

Domain opportunity merupakan hasil analisis dari domain lain.

Opportunity tidak hanya berupa paket mentah.

Opportunity adalah peluang yang sudah diberi konteks.

Opportunity dapat memiliki:

- sumber data;
- institusi terkait;
- kebutuhan;
- kategori;
- produk relevan;
- principal relevan;
- nilai anggaran;
- skor prioritas;
- alasan rekomendasi;
- status tindak lanjut.

Domain ini menjadi pusat aktivitas bisnis NovaNusa.

---

## Domain Contact Intelligence

Domain contact intelligence mencakup informasi kontak publik institusi.

Termasuk:

- website;
- email;
- telepon;
- alamat;
- unit kerja;
- jabatan umum;
- sumber kontak;
- tingkat keyakinan;
- status validasi.

Contact intelligence harus digunakan secara etis dan hanya berdasarkan sumber yang sah.

---

# Batasan Sistem

NovaNusa harus memiliki batasan yang jelas.

Batasan ini penting agar platform tidak berubah menjadi sistem yang terlalu luas dan kehilangan fokus.

---

## Bukan Sistem Pengadaan Resmi

NovaNusa bukan pengganti SiRUP.

NovaNusa bukan pengganti LPSE.

NovaNusa bukan pengganti e-Katalog.

NovaNusa tidak membuat paket pengadaan.

NovaNusa tidak mengubah data pengadaan resmi.

NovaNusa hanya membaca, mengolah, menganalisis, dan menyajikan kembali informasi sebagai intelligence.

---

## Bukan Sistem Transaksi

NovaNusa tidak menjalankan transaksi jual beli.

NovaNusa tidak menerima pembayaran dari institusi pemerintah.

NovaNusa tidak membuat kontrak pengadaan.

NovaNusa tidak memproses tender.

NovaNusa tidak mengirim penawaran resmi secara otomatis tanpa persetujuan manusia.

---

## Bukan Sistem Legal Decision

NovaNusa tidak memberikan keputusan hukum.

NovaNusa tidak menyatakan bahwa suatu tindakan pasti sah secara hukum.

NovaNusa hanya membantu analisis data.

Setiap keputusan hukum, kontrak, atau kepatuhan tetap harus dikaji oleh pihak yang berwenang.

---

## Bukan Sistem Spam

NovaNusa tidak boleh digunakan untuk mengirim pesan massal tanpa kendali.

Setiap komunikasi keluar harus:

- relevan;
- berbasis data;
- dapat dijelaskan;
- memiliki persetujuan pengguna;
- menghormati etika komunikasi bisnis.

---

## Bukan Sistem Scraping Bebas Tanpa Batas

NovaNusa tidak boleh mengambil data secara sembarangan.

Pengambilan data harus memperhatikan:

- sumber resmi;
- kepatutan;
- batas teknis sumber;
- etika penggunaan;
- kebutuhan bisnis yang jelas.

---

# Batas Penggunaan AI

AI dalam NovaNusa memiliki batas yang tegas.

AI boleh membantu, tetapi tidak boleh menjadi satu-satunya sumber kebenaran.

---

## AI Boleh Digunakan Untuk

AI boleh digunakan untuk:

- membaca teks panjang;
- melakukan klasifikasi awal;
- mengenali pola;
- menyarankan kategori;
- menyarankan produk;
- menyusun ringkasan;
- membantu pencarian;
- membuat draft komunikasi;
- menjelaskan hasil analisis.

---

## AI Tidak Boleh Digunakan Untuk

AI tidak boleh digunakan untuk:

- mengambil keputusan final tanpa validasi;
- mengubah data sumber resmi;
- menyatakan kepastian hukum;
- mengirim komunikasi bisnis tanpa approval;
- membuat klaim produk yang tidak didukung data;
- menyembunyikan alasan rekomendasi;
- menggantikan audit manusia pada kasus berisiko tinggi.

---

# Batas Integrasi Eksternal

NovaNusa dapat terhubung dengan sistem eksternal, tetapi integrasi harus memiliki batas yang jelas.

Integrasi dapat mencakup:

- sumber data pemerintah;
- sistem katalog produk;
- sistem CRM;
- email provider;
- dashboard internal;
- penyimpanan dokumen;
- AI provider;
- local AI model.

Setiap integrasi harus memenuhi prinsip:

- aman;
- dapat diaudit;
- dapat dihentikan;
- tidak mengunci sistem pada satu vendor;
- tidak merusak data utama;
- tidak menghilangkan kendali pengguna.

---

# Kapabilitas Inti

NovaNusa wajib memiliki kapabilitas inti berikut.

---

## 1. Entity Management

Sistem harus mampu mengelola entitas utama seperti:

- institusi;
- paket;
- produk;
- principal;
- kategori;
- kontak;
- opportunity;
- user.

Setiap entitas harus memiliki identitas yang jelas.

---

## 2. Search and Discovery

Sistem harus memungkinkan pengguna mencari dan menemukan informasi secara cepat.

Pencarian harus mendukung:

- nama institusi;
- kategori;
- produk;
- principal;
- wilayah;
- tahun;
- nilai anggaran;
- status peluang;
- kata kunci kebutuhan.

---

## 3. Matching Engine

Sistem harus memiliki mesin pencocokan antara kebutuhan dan solusi.

Matching engine harus mempertimbangkan:

- keyword;
- kategori;
- konteks;
- histori;
- produk;
- principal;
- confidence score;
- alasan pencocokan.

---

## 4. Scoring and Prioritization

Sistem harus mampu memberi skor pada peluang.

Skor dapat mempertimbangkan:

- nilai anggaran;
- kecocokan produk;
- relevansi principal;
- kualitas data kontak;
- urgensi;
- histori kebutuhan;
- tingkat keyakinan;
- potensi bisnis.

Skor harus dapat dijelaskan.

---

## 5. Dashboard and Reporting

Sistem harus menyajikan informasi melalui dashboard dan laporan.

Laporan dapat mencakup:

- distribusi peluang;
- top institusi;
- top kategori;
- top wilayah;
- top principal;
- pipeline status;
- tren periodik;
- hasil matching;
- kualitas data.

---

## 6. Human Review Workflow

Sistem harus menyediakan mekanisme review manusia.

Review diperlukan untuk:

- validasi peluang;
- validasi kontak;
- validasi hasil matching;
- approval komunikasi;
- koreksi kategori;
- perbaikan data.

Human review adalah bagian penting dari kualitas sistem.

---

# Prinsip Ekspansi

NovaNusa boleh berkembang ke domain baru selama tetap mengikuti visi utama.

Ekspansi harus memenuhi syarat:

- memperkuat procurement intelligence;
- memperkaya knowledge;
- meningkatkan kualitas insight;
- tidak merusak data inti;
- tidak mengubah identitas sistem;
- tidak membuat sistem kehilangan fokus;
- dapat dijelaskan dalam arsitektur modular.

Ekspansi yang tidak memenuhi syarat tersebut harus ditunda.

---

# Hal yang Tidak Termasuk Scope Awal

Beberapa hal secara eksplisit tidak termasuk dalam scope awal NovaNusa.

Hal-hal tersebut adalah:

- marketplace transaksi;
- sistem pembayaran;
- sistem tender resmi;
- sistem kontrak elektronik;
- sistem inventory penuh;
- sistem akuntansi;
- sistem HR;
- sistem legal automation;
- sistem pengganti CRM penuh;
- sistem pengadaan internal pemerintah;
- sistem pengambilan keputusan otomatis tanpa manusia.

Hal-hal tersebut dapat dipertimbangkan di masa depan hanya jika tidak mengganggu fokus utama platform.

---

# Ukuran Keberhasilan Scope

Ruang lingkup NovaNusa dianggap berhasil apabila sistem mampu:

- menjaga fokus pada procurement intelligence;
- menghindari fitur yang tidak relevan;
- menghubungkan data pemerintah dengan produk dan principal;
- menghasilkan opportunity yang dapat ditindaklanjuti;
- memberikan insight yang dapat dipercaya;
- mendukung sales dan manajemen;
- mempertahankan kendali manusia;
- tetap modular dan dapat berkembang.

Keberhasilan scope bukan diukur dari banyaknya fitur.

Keberhasilan scope diukur dari ketepatan sistem dalam menyelesaikan masalah inti.

---

# Penutup

Dokumen ini menetapkan batas resmi ruang lingkup NovaNusa.

Seluruh fitur, modul, dashboard, integrasi, dan penggunaan AI harus mengikuti batas yang telah dijelaskan dalam dokumen ini.

Apabila ada ide pengembangan baru, ide tersebut harus dievaluasi berdasarkan dokumen ini sebelum masuk ke tahap implementasi.

Dengan ruang lingkup yang jelas, NovaNusa dapat berkembang secara terarah, tidak melebar tanpa kendali, dan tetap konsisten sebagai platform intelligence untuk memahami kebutuhan institusi pemerintah Indonesia.

---

**Status Dokumen:** FINAL
