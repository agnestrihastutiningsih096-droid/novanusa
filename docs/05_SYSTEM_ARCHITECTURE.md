# 05 — NOVANUSA SYSTEM ARCHITECTURE

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan resmi arsitektur sistem NovaNusa.

Seluruh keputusan implementasi teknis, desain modul, integrasi data, antarmuka pengguna, orkestrasi AI, audit, dan pengembangan lanjutan wajib mengacu pada dokumen ini.

Dokumen ini disusun berdasarkan:

- `docs/00_PROJECT_CHARTER.md`
- `docs/01_SYSTEM_VISION.md`
- `docs/02_SYSTEM_SCOPE.md`
- `docs/03_DOMAIN_MODEL.md`
- `docs/04_DATA_ARCHITECTURE.md`

Dokumen ini tidak menggantikan dokumen sebelumnya, melainkan menerjemahkan fondasi proyek, visi sistem, ruang lingkup, domain model, dan arsitektur data menjadi rancangan sistem yang siap menjadi acuan implementasi.

---

# 1. Tujuan Dokumen

Dokumen ini bertujuan untuk menjelaskan arsitektur sistem NovaNusa secara menyeluruh, termasuk struktur modul, aliran kerja sistem, batas tanggung jawab komponen, prinsip integrasi, hubungan antara data dan fitur, serta cara sistem mendukung visi NovaNusa sebagai platform intelligence berbasis kebutuhan institusi.

Dokumen ini menjadi jembatan antara dokumen konseptual dan implementasi teknis.

Secara khusus, dokumen ini digunakan untuk:

1. Menentukan struktur sistem NovaNusa secara resmi.
2. Menjelaskan komponen utama yang wajib ada dalam sistem.
3. Menjelaskan hubungan antar modul.
4. Menjaga agar implementasi tidak menyimpang dari domain model.
5. Menjamin bahwa sistem tetap human-centered, explainable, auditable, dan scalable.
6. Menjadi acuan sebelum pembuatan kode aplikasi, API, database, dashboard, pipeline, dan modul AI.
7. Menjadi referensi utama untuk pengembangan bertahap NovaNusa.

---

# 2. Posisi Dokumen dalam Arsitektur NovaNusa

Dokumen ini berada setelah Data Architecture dan sebelum rancangan teknis implementasi.

Urutan fondasi dokumen NovaNusa adalah:

1. Project Charter
2. System Vision
3. System Scope
4. Domain Model
5. Data Architecture
6. System Architecture
7. Application Architecture
8. API Design
9. UI/UX Design
10. Implementation Roadmap

Dengan demikian, System Architecture tidak membahas kode, tetapi membahas bagaimana sistem harus dibentuk agar seluruh tujuan NovaNusa dapat diwujudkan secara konsisten.

---

# 3. Prinsip Arsitektur Sistem

NovaNusa dibangun dengan prinsip arsitektur berikut:

## 3.1 Human-Centered Intelligence

NovaNusa bukan sistem autopilot penuh.

Sistem harus membantu manusia memahami peluang, kebutuhan, risiko, dan rekomendasi, tetapi keputusan akhir tetap berada pada pengguna manusia.

Setiap rekomendasi sistem harus dapat ditinjau, dibandingkan, dan dikoreksi oleh pengguna.

## 3.2 Explainability by Design

Setiap output penting wajib memiliki alasan yang dapat dijelaskan.

Sistem tidak boleh hanya menampilkan hasil akhir seperti skor, prioritas, atau rekomendasi produk tanpa dasar yang jelas.

NovaNusa harus mampu menjawab:

- Mengapa kebutuhan ini terdeteksi?
- Mengapa institusi ini diprioritaskan?
- Mengapa produk ini direkomendasikan?
- Data apa yang menjadi dasar keputusan?
- Apakah ada risiko atau ketidakpastian?

## 3.3 Auditability

Setiap proses penting harus dapat ditelusuri kembali.

NovaNusa wajib menyimpan jejak sumber data, transformasi data, hasil pemrosesan, hasil scoring, rekomendasi, tindakan pengguna, dan status tindak lanjut.

Auditability diperlukan agar sistem dapat dipercaya, diperbaiki, dan dipertanggungjawabkan.

## 3.4 Single Source of Truth

Data inti NovaNusa harus memiliki sumber kebenaran yang jelas.

Sistem tidak boleh membuat banyak versi data institusi, kebutuhan, produk, atau rekomendasi tanpa mekanisme konsolidasi.

Jika terdapat data turunan, data tersebut harus tetap dapat ditelusuri ke data asal.

## 3.5 Modular and Extensible

NovaNusa harus dibangun secara modular.

Setiap modul memiliki tanggung jawab yang jelas dan dapat dikembangkan secara bertahap tanpa merusak modul lain.

Arsitektur harus mendukung perluasan ke domain baru, sumber data baru, jenis produk baru, tipe pengguna baru, dan kanal komunikasi baru.

## 3.6 Data-First, Not Feature-First

NovaNusa harus memprioritaskan kualitas model data dan alur data sebelum fitur visual.

Dashboard, AI assistant, rekomendasi, dan otomasi hanya boleh dibangun di atas data yang terstruktur, dapat diaudit, dan konsisten.

## 3.7 Safe Automation

Otomasi dalam NovaNusa harus dikendalikan oleh batas keamanan.

Sistem boleh membantu menyusun rekomendasi, draft komunikasi, ringkasan, dan prioritas, tetapi tindakan eksternal yang berdampak pada pihak lain harus memiliki mekanisme review dan approval.

---

# 4. Gambaran Besar Sistem

NovaNusa adalah platform intelligence yang mengubah data kebutuhan institusi menjadi insight, prioritas peluang, rekomendasi produk atau solusi, dan bahan tindak lanjut yang dapat digunakan manusia untuk mengambil keputusan.

Secara konseptual, sistem NovaNusa terdiri dari lapisan berikut:

1. Data Source Layer
2. Ingestion Layer
3. Normalization Layer
4. Knowledge Layer
5. Intelligence Layer
6. Recommendation Layer
7. Workflow Layer
8. Presentation Layer
9. Audit and Governance Layer

Setiap lapisan memiliki fungsi yang berbeda tetapi saling terhubung.

---

# 5. System Architecture Overview

Arsitektur sistem NovaNusa dapat dipahami sebagai alur berikut:

1. Sistem mengambil atau menerima data dari berbagai sumber.
2. Data mentah disimpan sebagai raw data.
3. Data dibersihkan, dinormalisasi, dan diperkaya.
4. Data dipetakan ke domain model NovaNusa.
5. Sistem mendeteksi kebutuhan, kategori, institusi, produk, peluang, dan sinyal prioritas.
6. Sistem menghasilkan scoring dan rekomendasi.
7. Pengguna meninjau hasil melalui dashboard.
8. Pengguna mengambil tindakan, seperti menyimpan insight, menandai peluang, menyiapkan komunikasi, atau membuat rencana tindak lanjut.
9. Sistem menyimpan jejak audit dari data, proses, rekomendasi, dan tindakan pengguna.

---

# 6. Komponen Utama Sistem

NovaNusa terdiri dari komponen utama berikut:

1. Data Source Manager
2. Data Ingestion Engine
3. Raw Data Repository
4. Data Normalization Engine
5. Entity Resolution Engine
6. Knowledge Repository
7. Need Detection Engine
8. Product and Solution Mapping Engine
9. Opportunity Scoring Engine
10. Recommendation Engine
11. AI Assistance Layer
12. Workflow and Review Engine
13. Dashboard and User Interface
14. Audit Log System
15. Configuration and Governance Layer

Setiap komponen dijelaskan pada bagian berikut.

---

# 7. Data Source Manager

Data Source Manager bertanggung jawab mengelola daftar sumber data yang digunakan oleh NovaNusa.

Sumber data dapat mencakup:

- Data kebutuhan institusi.
- Data pengadaan.
- Data paket.
- Data institusi.
- Data kategori.
- Data produk.
- Data principal.
- Data kontak resmi.
- Data historis interaksi.
- Data hasil kurasi internal.

Data Source Manager tidak hanya menyimpan alamat sumber data, tetapi juga metadata sumber data, seperti:

- Nama sumber.
- Jenis sumber.
- Status sumber.
- Frekuensi pembaruan.
- Format data.
- Tingkat kepercayaan.
- Tanggal terakhir diproses.
- Catatan keterbatasan data.

Komponen ini wajib mendukung prinsip traceability.

Setiap data yang masuk ke NovaNusa harus dapat diketahui berasal dari sumber mana.

---

# 8. Data Ingestion Engine

Data Ingestion Engine bertanggung jawab mengambil, menerima, atau memuat data dari sumber yang telah didefinisikan.

Fungsi utama Data Ingestion Engine adalah:

1. Mengambil data dari sumber eksternal atau internal.
2. Menyimpan data mentah tanpa mengubah makna aslinya.
3. Mencatat waktu pengambilan data.
4. Mencatat status proses ingestion.
5. Mendeteksi kegagalan ingestion.
6. Menyediakan log proses.

Data Ingestion Engine harus menjaga prinsip raw preservation.

Data mentah tidak boleh langsung ditimpa oleh data hasil normalisasi.

Raw data harus tetap tersedia untuk audit dan validasi ulang.

---

# 9. Raw Data Repository

Raw Data Repository adalah tempat penyimpanan data mentah.

Data dalam repository ini belum dinormalisasi dan belum dianggap sebagai data final.

Tujuan Raw Data Repository adalah:

1. Menyimpan data sebagaimana diterima dari sumber.
2. Menjadi bukti asal data.
3. Mendukung proses audit.
4. Memungkinkan reprocessing jika aturan normalisasi berubah.
5. Mencegah kehilangan konteks asli.

Raw Data Repository harus diperlakukan sebagai arsip data sumber.

Data di dalamnya tidak boleh digunakan langsung untuk rekomendasi akhir tanpa melalui proses normalisasi dan validasi.

---

# 10. Data Normalization Engine

Data Normalization Engine bertanggung jawab mengubah data mentah menjadi data yang lebih terstruktur, konsisten, dan siap digunakan oleh domain model.

Normalisasi dapat mencakup:

- Normalisasi nama institusi.
- Normalisasi nama daerah.
- Normalisasi kategori kebutuhan.
- Normalisasi format anggaran.
- Normalisasi tahun.
- Normalisasi status paket.
- Normalisasi nama produk.
- Normalisasi principal.
- Normalisasi kontak.
- Normalisasi istilah teknis.
- Normalisasi sinonim dan variasi penulisan.

Normalisasi tidak boleh menghapus nilai asli.

Setiap nilai hasil normalisasi harus tetap memiliki referensi ke nilai sumber.

Contoh prinsip:

- Nama asli institusi tetap disimpan.
- Nama institusi hasil normalisasi disimpan sebagai bentuk standar.
- Jika terdapat perubahan aturan normalisasi, hasil lama harus dapat ditinjau ulang.

---

# 11. Entity Resolution Engine

Entity Resolution Engine bertugas menyatukan entitas yang secara substansi sama tetapi muncul dalam variasi penulisan berbeda.

Entitas yang perlu diselesaikan meliputi:

- Institution
- Region
- Product
- Principal
- Category
- Contact
- Need
- Opportunity

Contoh permasalahan yang harus ditangani:

- Institusi yang sama memiliki beberapa variasi nama.
- Produk yang sama ditulis dengan nama berbeda.
- Kontak institusi muncul dari beberapa sumber.
- Kategori kebutuhan memiliki istilah teknis dan istilah umum.
- Principal memiliki variasi brand atau distributor.

Entity Resolution Engine tidak boleh melakukan penggabungan permanen tanpa jejak.

Setiap keputusan penggabungan harus memiliki:

- Entitas asal.
- Entitas hasil konsolidasi.
- Alasan penggabungan.
- Metode penggabungan.
- Confidence score.
- Status review bila diperlukan.

---

# 12. Knowledge Repository

Knowledge Repository adalah pusat pengetahuan terstruktur NovaNusa.

Komponen ini menyimpan hubungan antara entitas domain, seperti:

- Institusi memiliki kebutuhan.
- Kebutuhan berada dalam kategori.
- Kategori dapat dipenuhi oleh produk.
- Produk dimiliki oleh principal.
- Opportunity berasal dari kebutuhan.
- Recommendation berasal dari opportunity.
- User action berkaitan dengan recommendation.
- Audit log mencatat perubahan dan tindakan.

Knowledge Repository bukan sekadar database transaksional.

Ia adalah representasi pengetahuan NovaNusa mengenai institusi, kebutuhan, produk, peluang, dan konteks keputusan.

Knowledge Repository harus mendukung:

1. Query berdasarkan institusi.
2. Query berdasarkan kategori kebutuhan.
3. Query berdasarkan produk.
4. Query berdasarkan principal.
5. Query berdasarkan peluang.
6. Query berdasarkan skor prioritas.
7. Query berdasarkan status workflow.
8. Query berdasarkan sumber data.
9. Query berdasarkan riwayat audit.

---

# 13. Need Detection Engine

Need Detection Engine bertugas mendeteksi kebutuhan dari data yang tersedia.

Kebutuhan dapat berasal dari:

- Nama paket.
- Deskripsi paket.
- Kategori pengadaan.
- Spesifikasi teknis.
- Riwayat pengadaan.
- Pola institusi.
- Data tambahan yang dikurasi.

Need Detection Engine harus menghasilkan:

1. Need label.
2. Need category.
3. Evidence text.
4. Source reference.
5. Confidence score.
6. Risk flag bila terdapat ambiguitas.
7. Status review bila perlu.

Sistem tidak boleh menganggap semua kata kunci sebagai kebutuhan yang valid tanpa konteks.

Misalnya, istilah teknis harus dibaca bersama konteks paket, institusi, dan kategori.

Need Detection Engine harus mampu membedakan:

- Kebutuhan utama.
- Kebutuhan pendukung.
- Kebutuhan ambigu.
- Kebutuhan yang tidak relevan.
- Kebutuhan yang berisiko salah klasifikasi.

---

# 14. Product and Solution Mapping Engine

Product and Solution Mapping Engine bertugas mencocokkan kebutuhan dengan produk, solusi, kategori, atau principal yang relevan.

Mapping tidak boleh hanya berbasis kata kunci sederhana.

Mapping harus mempertimbangkan:

- Kategori kebutuhan.
- Spesifikasi kebutuhan.
- Ketersediaan produk.
- Relevansi produk.
- Kesesuaian institusi.
- Risiko mismatch.
- Kualitas data produk.
- Hubungan produk dengan principal.
- Tingkat keyakinan sistem.

Output mapping harus mencakup:

1. Need yang dipetakan.
2. Produk atau solusi yang direkomendasikan.
3. Alasan rekomendasi.
4. Evidence.
5. Confidence score.
6. Risk flag.
7. Status review.

Jika sistem tidak yakin, sistem harus menyatakan ketidakpastian dan menandai item untuk review.

---

# 15. Opportunity Scoring Engine

Opportunity Scoring Engine bertugas memberikan skor prioritas pada peluang.

Skor tidak boleh menjadi angka tanpa penjelasan.

Setiap skor harus dapat dijelaskan berdasarkan faktor-faktor yang jelas.

Faktor scoring dapat mencakup:

- Besaran anggaran.
- Relevansi kebutuhan.
- Kecocokan produk.
- Kejelasan institusi.
- Ketersediaan kontak.
- Tingkat kompetisi.
- Urgensi waktu.
- Kualitas data.
- Risiko mismatch.
- Potensi nilai strategis.
- Riwayat peluang serupa.
- Status workflow.

Output scoring harus mencakup:

1. Opportunity score.
2. Score breakdown.
3. Faktor pendukung.
4. Faktor pengurang.
5. Confidence level.
6. Risk level.
7. Rekomendasi tindakan.

Opportunity Scoring Engine harus bersifat configurable.

Perubahan bobot scoring harus dicatat dan tidak boleh menghapus riwayat scoring lama.

---

# 16. Recommendation Engine

Recommendation Engine bertugas menghasilkan rekomendasi yang dapat digunakan oleh pengguna.

Rekomendasi dapat berupa:

- Institusi prioritas.
- Kebutuhan prioritas.
- Produk yang sesuai.
- Principal yang relevan.
- Peluang yang layak ditindaklanjuti.
- Risiko yang perlu diperiksa.
- Draft komunikasi.
- Langkah berikutnya.
- Status hold atau review.

Setiap rekomendasi wajib memiliki:

1. Judul rekomendasi.
2. Entitas yang direkomendasikan.
3. Alasan rekomendasi.
4. Evidence.
5. Confidence score.
6. Risiko.
7. Status review.
8. Tindakan yang disarankan.

Recommendation Engine tidak boleh menyembunyikan alasan.

Pengguna harus dapat memahami mengapa rekomendasi muncul.

---

# 17. AI Assistance Layer

AI Assistance Layer adalah lapisan bantuan kecerdasan buatan dalam NovaNusa.

AI dapat digunakan untuk:

- Merangkum kebutuhan institusi.
- Menjelaskan peluang.
- Membantu klasifikasi.
- Membantu mapping produk.
- Membantu menyusun draft komunikasi.
- Membantu menjelaskan alasan rekomendasi.
- Membantu membuat insight.
- Membantu pengguna memahami data kompleks.

AI tidak boleh menjadi sumber kebenaran tunggal.

AI harus bekerja di atas data yang telah terstruktur dan dapat diaudit.

Setiap output AI yang penting harus:

1. Memiliki konteks data.
2. Tidak mengarang informasi.
3. Menyebutkan dasar data.
4. Memberikan indikasi ketidakpastian.
5. Dapat direview oleh pengguna.
6. Tidak melakukan tindakan eksternal tanpa approval.

AI Assistance Layer harus tunduk pada prinsip human-in-the-loop.

---

# 18. Workflow and Review Engine

Workflow and Review Engine mengatur status dan proses kerja dalam NovaNusa.

Status workflow dapat mencakup:

- New
- Processed
- Matched
- Scored
- Recommended
- Review Required
- Approved
- Hold
- Rejected
- Follow Up
- Completed
- Archived

Workflow harus memungkinkan pengguna melakukan:

- Review peluang.
- Menyetujui rekomendasi.
- Menahan item yang berisiko.
- Menolak rekomendasi.
- Memberi catatan.
- Mengubah prioritas.
- Menandai tindak lanjut.
- Menyimpan riwayat keputusan.

Setiap perubahan status harus dicatat dalam audit log.

Tidak boleh ada perubahan status penting tanpa timestamp dan user context.

---

# 19. Dashboard and User Interface

Dashboard adalah lapisan presentasi utama NovaNusa.

Dashboard harus membantu pengguna memahami data, bukan sekadar menampilkan tabel.

Dashboard wajib mendukung:

1. Ringkasan peluang.
2. Daftar institusi.
3. Daftar kebutuhan.
4. Daftar kategori.
5. Daftar produk.
6. Daftar principal.
7. Opportunity scoring.
8. Recommendation review.
9. Risk flag.
10. Evidence view.
11. Audit trail.
12. Filter dan pencarian.
13. Detail view per entitas.
14. Workflow action.

Dashboard harus dirancang agar pengguna dapat menjawab:

- Institusi mana yang paling penting?
- Kebutuhan apa yang muncul?
- Produk apa yang relevan?
- Peluang mana yang siap ditindaklanjuti?
- Peluang mana yang perlu review?
- Mengapa sistem memberikan rekomendasi tersebut?
- Data apa yang mendukung keputusan?
- Apa langkah berikutnya?

Dashboard tidak boleh hanya menjadi tampilan data mentah.

Dashboard harus menjadi decision support interface.

---

# 20. Audit Log System

Audit Log System mencatat seluruh kejadian penting dalam sistem.

Audit log harus mencakup:

- Data ingestion.
- Data normalization.
- Entity resolution.
- Need detection.
- Product mapping.
- Scoring.
- Recommendation generation.
- AI output.
- User review.
- Approval.
- Rejection.
- Status change.
- Configuration change.
- Manual correction.
- Export atau tindakan eksternal.

Audit log minimal harus memiliki:

1. Event ID.
2. Event type.
3. Entity type.
4. Entity ID.
5. Previous value bila relevan.
6. New value bila relevan.
7. User atau system actor.
8. Timestamp.
9. Source reference.
10. Notes.
11. Confidence atau risk context bila relevan.

Audit log tidak boleh dianggap fitur tambahan.

Audit log adalah bagian inti dari arsitektur NovaNusa.

---

# 21. Configuration and Governance Layer

Configuration and Governance Layer menyimpan aturan yang dapat dikonfigurasi tanpa mengubah prinsip sistem.

Konfigurasi dapat mencakup:

- Bobot scoring.
- Kategori kebutuhan.
- Kata kunci deteksi.
- Rule mapping produk.
- Risk threshold.
- Approval threshold.
- Status workflow.
- Source priority.
- AI prompt policy.
- Review policy.
- Export policy.

Setiap perubahan konfigurasi harus dicatat.

Konfigurasi tidak boleh mengubah domain model secara sembarangan.

Jika perubahan konfigurasi berdampak pada struktur entitas inti, perubahan tersebut harus melalui revisi dokumen arsitektur.

---

# 22. Hubungan Sistem dengan Domain Model

Arsitektur sistem NovaNusa harus mengikuti domain model yang telah ditetapkan.

Setiap modul sistem harus beroperasi di atas entitas domain resmi, yaitu:

- Institution
- Region
- Need
- Need Category
- Procurement Package
- Product
- Product Category
- Principal
- Opportunity
- Recommendation
- Contact
- User
- Workflow Status
- Audit Log

Sistem tidak boleh membuat entitas inti baru tanpa justifikasi arsitektural.

Jika implementasi membutuhkan entitas teknis tambahan, entitas tersebut harus bersifat pendukung dan tidak mengaburkan domain model utama.

---

# 23. Hubungan Sistem dengan Data Architecture

System Architecture harus menjalankan prinsip Data Architecture.

Artinya:

1. Raw data harus tetap disimpan.
2. Normalized data harus terpisah dari raw data.
3. Derived data harus dapat ditelusuri.
4. Data audit harus tersedia.
5. Data entity harus konsisten dengan domain model.
6. Data tidak boleh kehilangan konteks sumber.
7. Data rekomendasi harus memiliki evidence.
8. AI output harus dapat dikaitkan dengan data sumber.
9. Workflow action harus tersimpan sebagai event.
10. Sistem harus mendukung reprocessing.

System Architecture tidak boleh memperlakukan data hanya sebagai tabel aplikasi.

Data adalah fondasi intelligence NovaNusa.

---

# 24. Aliran Data Utama

Aliran data utama NovaNusa adalah sebagai berikut:

1. Source data diterima oleh Data Source Manager.
2. Data Ingestion Engine mengambil data dari source.
3. Raw Data Repository menyimpan data asli.
4. Data Normalization Engine membersihkan dan menstandarkan data.
5. Entity Resolution Engine menyatukan entitas yang sama.
6. Knowledge Repository menyimpan relasi antar entitas.
7. Need Detection Engine mendeteksi kebutuhan.
8. Product Mapping Engine mencocokkan kebutuhan dengan produk.
9. Opportunity Scoring Engine memberi skor peluang.
10. Recommendation Engine menghasilkan rekomendasi.
11. AI Assistance Layer membantu menjelaskan dan merangkum.
12. Dashboard menampilkan insight kepada pengguna.
13. Workflow Engine mencatat tindakan pengguna.
14. Audit Log System menyimpan seluruh jejak proses.

---

# 25. Aliran Keputusan Pengguna

Aliran keputusan pengguna dalam NovaNusa adalah:

1. Pengguna melihat daftar peluang.
2. Pengguna membuka detail opportunity.
3. Sistem menampilkan kebutuhan, evidence, produk relevan, skor, dan risiko.
4. Pengguna meninjau rekomendasi.
5. Pengguna dapat menyetujui, menahan, menolak, atau memberi catatan.
6. Jika disetujui, peluang dapat masuk ke tahap tindak lanjut.
7. Jika perlu review, peluang tetap berada dalam status review.
8. Jika ditolak, alasan penolakan dicatat.
9. Semua tindakan tersimpan di audit log.

Keputusan pengguna adalah bagian dari pengetahuan sistem.

NovaNusa harus belajar secara terstruktur dari tindakan pengguna, tetapi tidak boleh mengubah aturan inti tanpa governance.

---

# 26. Arsitektur Modul Berdasarkan Fungsi

NovaNusa dapat dibagi menjadi modul fungsional berikut:

## 26.1 Data Module

Mengelola sumber data, ingestion, raw data, normalisasi, dan validasi.

## 26.2 Knowledge Module

Mengelola entitas domain dan relasi antar entitas.

## 26.3 Intelligence Module

Mengelola deteksi kebutuhan, mapping produk, scoring, dan rekomendasi.

## 26.4 AI Module

Mengelola bantuan AI, ringkasan, penjelasan, draft, dan reasoning support.

## 26.5 Workflow Module

Mengelola status, review, approval, hold, rejection, dan follow-up.

## 26.6 Dashboard Module

Mengelola tampilan pengguna, filter, detail, evidence, dan decision interface.

## 26.7 Audit Module

Mengelola jejak proses, perubahan data, tindakan pengguna, dan governance.

## 26.8 Configuration Module

Mengelola aturan sistem, bobot scoring, threshold, kategori, dan policy.

---

# 27. Batas Tanggung Jawab Modul

Setiap modul harus memiliki batas tanggung jawab yang jelas.

Data Module tidak boleh mengambil keputusan bisnis final.

Knowledge Module tidak boleh mengubah data sumber tanpa audit.

Intelligence Module tidak boleh menyembunyikan evidence.

AI Module tidak boleh membuat fakta baru tanpa basis data.

Workflow Module tidak boleh melewati approval untuk tindakan penting.

Dashboard Module tidak boleh menampilkan rekomendasi tanpa penjelasan.

Audit Module tidak boleh bersifat opsional.

Configuration Module tidak boleh mengubah prinsip domain secara bebas.

---

# 28. Prinsip Integrasi Antar Modul

Integrasi antar modul harus mengikuti prinsip berikut:

1. Modul berkomunikasi melalui data yang terstruktur.
2. Setiap output penting memiliki metadata.
3. Setiap proses penting menghasilkan audit event.
4. Modul tidak boleh bergantung pada data mentah jika data terstruktur tersedia.
5. Modul AI harus menerima konteks dari Knowledge Repository.
6. Dashboard harus membaca dari data yang telah diproses, bukan langsung dari raw data.
7. Workflow action harus memperbarui status tanpa menghapus riwayat.
8. Recommendation harus dapat ditelusuri ke need, product, dan evidence.

---

# 29. Arsitektur Human-in-the-Loop

NovaNusa wajib menerapkan human-in-the-loop pada proses penting.

Proses yang membutuhkan review manusia meliputi:

- Rekomendasi dengan confidence rendah.
- Mapping produk yang ambigu.
- Institusi dengan data kontak tidak jelas.
- Opportunity dengan risiko mismatch.
- AI-generated communication draft.
- Perubahan status menjadi approved.
- Tindakan eksternal yang melibatkan pihak ketiga.
- Perubahan rule penting.
- Penggabungan entitas yang berisiko.

Human-in-the-loop bukan hambatan, tetapi mekanisme keselamatan dan kualitas.

---

# 30. Arsitektur Explainability

Explainability harus tersedia pada setiap decision point.

Sistem harus menyediakan explanation layer untuk:

- Need detection.
- Product matching.
- Opportunity scoring.
- Recommendation.
- Risk flag.
- Workflow suggestion.
- AI-generated summary.

Explanation layer harus menjawab:

1. Apa yang diputuskan sistem?
2. Mengapa sistem membuat keputusan itu?
3. Data apa yang digunakan?
4. Seberapa yakin sistem?
5. Apa risiko yang terdeteksi?
6. Apa yang perlu dicek pengguna?

---

# 31. Arsitektur Risk Management

NovaNusa harus memiliki mekanisme risk management bawaan.

Risk flag dapat diberikan pada:

- Data tidak lengkap.
- Data sumber tidak jelas.
- Institusi ambigu.
- Kontak tidak valid.
- Kategori kebutuhan tidak pasti.
- Produk tidak benar-benar cocok.
- Principal tidak tersedia.
- Skor terlalu dipengaruhi satu faktor.
- AI output terlalu spekulatif.
- Opportunity perlu review manual.

Risk level dapat berupa:

- Low
- Medium
- High
- Critical

Risk flag harus terlihat di dashboard dan tersimpan dalam audit log.

---

# 32. Arsitektur Approval

Approval adalah mekanisme formal sebelum tindakan penting dilakukan.

Tindakan yang memerlukan approval dapat mencakup:

- Menandai opportunity sebagai siap ditindaklanjuti.
- Menggunakan rekomendasi produk untuk komunikasi eksternal.
- Mengirim draft komunikasi.
- Mengekspor data untuk tindakan bisnis.
- Mengubah status final.
- Mengubah konfigurasi berisiko.

Approval harus mencatat:

1. Siapa yang menyetujui.
2. Apa yang disetujui.
3. Kapan disetujui.
4. Berdasarkan data apa.
5. Catatan approval.
6. Status sebelum dan sesudah approval.

---

# 33. Arsitektur AI Safety

AI dalam NovaNusa harus dibatasi oleh aturan keselamatan.

AI tidak boleh:

- Mengarang data institusi.
- Mengarang kontak.
- Mengarang produk.
- Mengarang principal.
- Mengarang status pengadaan.
- Menghapus konteks ketidakpastian.
- Mengirim komunikasi tanpa approval.
- Mengubah data master tanpa review.
- Menghasilkan klaim yang tidak didukung data.

AI boleh:

- Membantu merangkum.
- Membantu menjelaskan.
- Membantu mengklasifikasi dengan evidence.
- Membantu menyusun draft.
- Membantu membandingkan alternatif.
- Membantu memberi saran tindak lanjut.
- Membantu menemukan inkonsistensi.

AI output harus selalu dikaitkan dengan sumber data dan status review.

---

# 34. Arsitektur Dashboard

Dashboard NovaNusa harus terdiri dari beberapa area utama:

## 34.1 Executive Overview

Menampilkan ringkasan peluang, jumlah institusi, kategori utama, peluang prioritas, dan status workflow.

## 34.2 Institution Intelligence

Menampilkan profil institusi, kebutuhan, riwayat peluang, kategori dominan, kontak, dan status tindak lanjut.

## 34.3 Need Intelligence

Menampilkan daftar kebutuhan yang terdeteksi, kategori, evidence, confidence, dan risiko.

## 34.4 Product Matching

Menampilkan hubungan antara kebutuhan dan produk yang relevan.

## 34.5 Opportunity Pipeline

Menampilkan peluang berdasarkan status, skor, risiko, dan prioritas.

## 34.6 Recommendation Review

Menampilkan rekomendasi yang perlu disetujui, ditahan, atau ditolak.

## 34.7 Audit View

Menampilkan riwayat perubahan, proses, dan tindakan pengguna.

Dashboard harus mendukung drill-down dari ringkasan menuju detail evidence.

---

# 35. Arsitektur Search dan Filter

NovaNusa harus memiliki kemampuan pencarian dan filter yang kuat.

Filter minimal meliputi:

- Institusi.
- Wilayah.
- Kategori kebutuhan.
- Produk.
- Principal.
- Skor peluang.
- Status workflow.
- Confidence level.
- Risk level.
- Tahun.
- Sumber data.
- Status review.
- Status approval.

Search harus mendukung pencarian berdasarkan:

- Nama institusi.
- Nama paket.
- Kata kunci kebutuhan.
- Nama produk.
- Nama principal.
- Kategori.
- Catatan pengguna.

Search dan filter tidak boleh merusak konteks data.

Hasil pencarian tetap harus menampilkan evidence dan status.

---

# 36. Arsitektur Reporting

Reporting dalam NovaNusa harus mendukung pengambilan keputusan strategis.

Report dapat mencakup:

- Distribusi kebutuhan per kategori.
- Distribusi peluang per wilayah.
- Top institusi berdasarkan skor.
- Top produk berdasarkan relevansi.
- Gap antara kebutuhan dan ketersediaan produk.
- Principal yang paling relevan.
- Opportunity pipeline.
- Review backlog.
- Risk distribution.
- Data quality report.
- Contactability report.

Report harus dapat ditelusuri ke data asal.

Tidak boleh ada angka agregat tanpa definisi perhitungan yang jelas.

---

# 37. Arsitektur Data Quality

Data Quality harus menjadi bagian dari sistem.

Dimensi kualitas data meliputi:

- Completeness
- Accuracy
- Consistency
- Freshness
- Traceability
- Validity
- Uniqueness
- Relevance

NovaNusa harus dapat menandai data yang:

- Tidak lengkap.
- Duplikat.
- Berpotensi salah.
- Sudah usang.
- Tidak dapat diverifikasi.
- Memerlukan review.

Data quality score dapat digunakan sebagai faktor scoring opportunity.

---

# 38. Arsitektur Security dan Access Control

NovaNusa harus memiliki kontrol akses sesuai peran pengguna.

Peran awal yang dapat digunakan:

- Owner
- Admin
- Analyst
- Reviewer
- Operator
- Viewer

Setiap peran memiliki batas kewenangan.

Contoh:

- Viewer hanya melihat data.
- Analyst dapat meninjau dan memberi catatan.
- Reviewer dapat menyetujui rekomendasi tertentu.
- Admin dapat mengatur konfigurasi.
- Owner memiliki akses strategis penuh.

Tindakan sensitif harus dibatasi oleh role dan tercatat dalam audit log.

---

# 39. Arsitektur Privacy dan Data Responsibility

NovaNusa harus menangani data secara bertanggung jawab.

Prinsip yang harus dijaga:

1. Gunakan data sesuai tujuan sistem.
2. Hindari pengumpulan data yang tidak relevan.
3. Simpan sumber data dan konteks penggunaan.
4. Jangan menampilkan data sensitif tanpa kebutuhan.
5. Pastikan kontak dan data institusi digunakan secara etis.
6. Sediakan audit untuk penggunaan data.
7. Hindari komunikasi otomatis tanpa review manusia.

NovaNusa harus menjadi platform intelligence yang bertanggung jawab, bukan alat spam atau eksploitasi data.

---

# 40. Arsitektur Scalability

NovaNusa harus dapat berkembang secara bertahap.

Skalabilitas sistem mencakup:

- Penambahan sumber data.
- Penambahan kategori kebutuhan.
- Penambahan produk dan principal.
- Penambahan wilayah.
- Penambahan user.
- Penambahan workflow.
- Penambahan kanal komunikasi.
- Penambahan model AI.
- Penambahan dashboard.
- Penambahan report.

Arsitektur modular memungkinkan peningkatan skala tanpa membangun ulang seluruh sistem.

---

# 41. Arsitektur Maintainability

Sistem harus mudah dipelihara.

Maintainability didukung oleh:

- Modul yang jelas.
- Dokumentasi arsitektur.
- Data model yang stabil.
- Audit log.
- Konfigurasi terpisah.
- Workflow eksplisit.
- Pemisahan raw, normalized, dan derived data.
- Penamaan entitas yang konsisten.
- Batas tanggung jawab yang jelas.

Implementasi yang sulit dijelaskan harus dianggap belum sesuai dengan prinsip NovaNusa.

---

# 42. Arsitektur Extensibility

NovaNusa harus siap diperluas ke domain lain.

Walaupun fokus awal dapat berada pada kebutuhan institusi dan pencocokan produk, arsitektur harus memungkinkan perluasan ke:

- Domain pendidikan.
- Domain kesehatan.
- Domain teknologi informasi.
- Domain infrastruktur.
- Domain alat kesehatan.
- Domain jasa.
- Domain principal discovery.
- Domain market intelligence.
- Domain sales intelligence.
- Domain partnership intelligence.

Perluasan harus tetap mengikuti domain model dan tidak merusak fondasi inti.

---

# 43. Arsitektur Observability

Sistem harus dapat diamati dan dipantau.

Observability mencakup:

- Status ingestion.
- Jumlah data yang diproses.
- Error proses.
- Status normalisasi.
- Status entity resolution.
- Jumlah rekomendasi.
- Jumlah item review.
- Jumlah approval.
- Kinerja scoring.
- Kualitas data.
- Aktivitas user.
- Status AI generation.
- Audit event.

Observability membantu pengembangan, debugging, dan pengawasan kualitas.

---

# 44. Arsitektur Error Handling

Kesalahan sistem harus ditangani secara aman.

Jika terjadi error:

1. Sistem harus mencatat error.
2. Sistem tidak boleh menghapus data asal.
3. Sistem tidak boleh menghasilkan rekomendasi tanpa data valid.
4. Sistem harus menandai item bermasalah.
5. Sistem harus memberi pesan yang dapat dipahami pengguna.
6. Sistem harus memungkinkan retry atau reprocessing.
7. Sistem harus menjaga audit trail.

Error bukan hanya masalah teknis, tetapi juga bagian dari kualitas intelligence.

---

# 45. Arsitektur Reprocessing

NovaNusa harus mendukung reprocessing.

Reprocessing diperlukan ketika:

- Sumber data diperbarui.
- Aturan normalisasi berubah.
- Rule deteksi kebutuhan diperbaiki.
- Rule mapping produk diperbarui.
- Bobot scoring berubah.
- Data produk diperbarui.
- Data principal diperbarui.
- Hasil audit menemukan kesalahan.
- Sistem AI diperbaiki.

Reprocessing harus menjaga riwayat hasil sebelumnya.

Hasil lama tidak boleh hilang tanpa catatan.

---

# 46. Arsitektur Versioning

Versioning diperlukan untuk menjaga konsistensi sistem.

Objek yang perlu memiliki versi meliputi:

- Rule deteksi kebutuhan.
- Rule mapping produk.
- Bobot scoring.
- Prompt AI.
- Konfigurasi workflow.
- Kategori.
- Dataset.
- Model rekomendasi.
- Dokumen arsitektur.

Versioning memungkinkan sistem menjelaskan mengapa hasil pada waktu tertentu berbeda dengan hasil setelah pembaruan.

---

# 47. Arsitektur Export

Export data harus dikendalikan.

Export dapat berupa:

- CSV.
- Spreadsheet.
- PDF report.
- Ringkasan peluang.
- Daftar institusi.
- Daftar rekomendasi.
- Draft komunikasi.
- Report strategis.

Setiap export penting harus mencatat:

1. Siapa yang melakukan export.
2. Data apa yang diekspor.
3. Kapan export dilakukan.
4. Filter yang digunakan.
5. Tujuan export bila tersedia.
6. Status approval bila diperlukan.

Export tidak boleh melewati prinsip auditability.

---

# 48. Arsitektur Communication Support

NovaNusa dapat mendukung komunikasi, tetapi bukan sistem spam otomatis.

Communication Support dapat mencakup:

- Draft email.
- Draft pesan.
- Ringkasan institusi.
- Rekomendasi produk.
- Lampiran penawaran.
- Catatan follow-up.
- Status komunikasi.

Setiap komunikasi eksternal harus melalui review manusia.

AI boleh membantu menyusun draft, tetapi pengguna harus menyetujui sebelum digunakan.

---

# 49. Arsitektur Opportunity Lifecycle

Lifecycle opportunity dalam NovaNusa adalah:

1. Detected
2. Normalized
3. Classified
4. Matched
5. Scored
6. Recommended
7. Reviewed
8. Approved atau Held atau Rejected
9. Followed Up
10. Completed atau Archived

Setiap tahap harus memiliki timestamp dan status.

Opportunity tidak boleh berpindah tahap tanpa aturan yang jelas.

---

# 50. Arsitektur Recommendation Lifecycle

Lifecycle recommendation adalah:

1. Generated
2. Explained
3. Risk Checked
4. Presented
5. Reviewed
6. Approved atau Rejected atau Held
7. Used atau Archived

Recommendation harus selalu terkait dengan:

- Opportunity.
- Need.
- Product atau solution.
- Evidence.
- Confidence score.
- Risk flag.
- User action.

---

# 51. Arsitektur Contact Intelligence

Contact Intelligence bertugas mengelola informasi kontak institusi secara hati-hati.

Data kontak harus memiliki:

- Source.
- Confidence.
- Validity status.
- Last checked date.
- Contact type.
- Institution relation.
- Notes.
- Risk flag bila ada.

Sistem tidak boleh menggunakan kontak yang tidak jelas tanpa review.

Kontak resmi lebih diutamakan daripada kontak tidak resmi.

Jika terdapat beberapa kontak, sistem harus menampilkan pilihan dan konteksnya.

---

# 52. Arsitektur Principal Intelligence

Principal Intelligence bertugas menghubungkan kebutuhan pasar dengan principal atau pemilik produk.

Sistem harus dapat menjawab:

- Principal mana yang relevan dengan kebutuhan tertentu?
- Produk apa yang dimiliki principal?
- Kategori apa yang dikuasai principal?
- Peluang institusi apa yang cocok untuk principal?
- Gap produk apa yang perlu dicari principalnya?

Principal Intelligence mendukung strategi bisnis NovaNusa sebagai platform pencocokan kebutuhan dan supply.

---

# 53. Arsitektur Product Intelligence

Product Intelligence bertugas mengelola produk sebagai entitas strategis.

Produk tidak hanya disimpan sebagai daftar barang, tetapi sebagai bagian dari knowledge system.

Produk harus memiliki:

- Nama.
- Kategori.
- Principal.
- Spesifikasi.
- Relevansi kebutuhan.
- Status ketersediaan.
- Catatan mapping.
- Risiko mismatch.
- Source.
- Version bila berubah.

Product Intelligence harus mendukung pencocokan kebutuhan secara explainable.

---

# 54. Arsitektur Institution Intelligence

Institution Intelligence bertugas membangun profil institusi.

Profil institusi dapat mencakup:

- Nama institusi.
- Wilayah.
- Jenis institusi.
- Kebutuhan yang terdeteksi.
- Riwayat opportunity.
- Kategori dominan.
- Kontak.
- Status pipeline.
- Catatan pengguna.
- Risk flag.
- Data quality score.

Institution Intelligence membantu pengguna memahami konteks, bukan hanya melihat nama institusi.

---

# 55. Arsitektur Need Intelligence

Need Intelligence bertugas memahami pola kebutuhan.

Need Intelligence harus dapat menjawab:

- Kebutuhan apa yang muncul?
- Dari institusi mana?
- Dalam kategori apa?
- Seberapa besar peluangnya?
- Produk apa yang dapat memenuhi?
- Apakah ada gap produk?
- Apakah kebutuhan tersebut jelas atau ambigu?
- Apakah perlu review?

Need Intelligence adalah pusat nilai NovaNusa.

---

# 56. Arsitektur Governance Dokumen

Dokumen System Architecture ini bersifat final sebagai acuan implementasi awal.

Perubahan terhadap dokumen ini hanya boleh dilakukan jika:

1. Terdapat perubahan Project Charter.
2. Terdapat perubahan System Vision.
3. Terdapat perubahan System Scope.
4. Terdapat perubahan Domain Model.
5. Terdapat perubahan Data Architecture.
6. Terdapat kebutuhan arsitektural baru yang disetujui.

Perubahan tidak boleh dilakukan hanya karena preferensi implementasi teknis sesaat.

---

# 57. Batasan Arsitektur

Dokumen ini tidak membahas:

- Detail kode.
- Nama framework.
- Struktur folder aplikasi.
- Skema database final.
- Endpoint API.
- Desain layar detail.
- Implementasi model AI tertentu.
- Deployment teknis.
- Infrastruktur cloud tertentu.

Hal-hal tersebut akan dibahas dalam dokumen lanjutan.

Namun, semua dokumen teknis lanjutan wajib tunduk pada prinsip dan struktur dalam dokumen ini.

---

# 58. Keputusan Arsitektur Final

Berdasarkan fondasi NovaNusa, keputusan arsitektur final adalah:

1. NovaNusa menggunakan arsitektur modular berbasis data dan knowledge.
2. Raw data, normalized data, derived data, dan audit data harus dipisahkan secara konseptual.
3. Sistem wajib memiliki explainability pada setiap rekomendasi penting.
4. AI digunakan sebagai assistance layer, bukan decision authority.
5. Workflow review dan approval adalah bagian inti sistem.
6. Audit log adalah komponen wajib.
7. Dashboard harus berfungsi sebagai decision support interface.
8. Entity resolution harus dilakukan secara hati-hati dan dapat diaudit.
9. Opportunity scoring harus dapat dijelaskan.
10. Product mapping harus menyertakan evidence dan confidence.
11. Sistem harus mendukung reprocessing dan versioning.
12. NovaNusa harus siap diperluas ke domain dan sumber data baru.

---

# 59. Implikasi untuk Implementasi Selanjutnya

Dokumen ini menjadi acuan untuk penyusunan dokumen berikutnya.

Dokumen lanjutan yang direkomendasikan adalah:

1. `docs/06_APPLICATION_ARCHITECTURE.md`
2. `docs/07_API_DESIGN.md`
3. `docs/08_DATABASE_SCHEMA.md`
4. `docs/09_UI_UX_ARCHITECTURE.md`
5. `docs/10_IMPLEMENTATION_ROADMAP.md`

Setiap dokumen lanjutan harus menjaga konsistensi dengan System Architecture ini.

---

# 60. Penutup

System Architecture NovaNusa dirancang untuk memastikan bahwa sistem berkembang sebagai platform intelligence yang kuat, dapat dipercaya, dapat diaudit, dan berpusat pada manusia.

Arsitektur ini menempatkan data sebagai fondasi, knowledge sebagai struktur, intelligence sebagai mesin analisis, AI sebagai asisten, workflow sebagai pengendali tindakan, dashboard sebagai antarmuka keputusan, dan audit sebagai penjaga kepercayaan.

Dengan arsitektur ini, NovaNusa siap dikembangkan secara bertahap menjadi platform yang mampu membaca kebutuhan institusi, memetakan peluang, mencocokkan produk dan principal, membantu pengambilan keputusan, serta mendukung proses bisnis secara profesional dan bertanggung jawab.

Seluruh implementasi NovaNusa wajib menjaga konsistensi dengan dokumen ini.

---

**Status Dokumen:** FINAL
