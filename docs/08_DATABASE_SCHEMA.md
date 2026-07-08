# 08 — NOVANUSA DATABASE SCHEMA

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan permanen mengenai rancangan skema basis data NovaNusa.

Dokumen ini mendefinisikan struktur logis seluruh data yang akan dikelola sistem, hubungan antarkelompok data, prinsip identifikasi data, kepemilikan data, serta standar konsistensi yang wajib digunakan oleh seluruh implementasi database di masa depan.

Dokumen ini bersifat implementation-independent. Seluruh isi dokumen menjelaskan struktur konseptual database tanpa mengikat pada DBMS tertentu.

---

# Tujuan Dokumen

Database Schema bertujuan untuk:

- menjadi satu-satunya referensi struktur data NovaNusa;
- menjaga konsistensi seluruh domain data;
- memastikan seluruh modul menggunakan definisi data yang sama;
- menghindari duplikasi entitas;
- mendukung auditability;
- mendukung explainability AI;
- menjaga integritas data lintas modul;
- mempermudah pengembangan bertahap;
- mendukung skalabilitas nasional;
- menyediakan fondasi bagi analitik dan AI.

---

# Posisi Database Schema

Dalam blueprint NovaNusa, Database Schema berada setelah:

- Project Charter
- System Vision
- System Scope
- Domain Model
- Data Architecture
- System Architecture
- Application Architecture
- API Design

Database Schema menjadi acuan langsung bagi:

- Logical Data Model
- Physical Data Model
- Database Migration
- ETL
- Data Warehouse
- Search Engine
- Vector Store
- Graph Database
- Backup Strategy
- Disaster Recovery
- Analytics
- AI Engine

---

# Filosofi Perancangan Database

NovaNusa dibangun sebagai platform intelligence nasional.

Karena itu struktur data tidak hanya menyimpan informasi, tetapi juga pengetahuan, hubungan antardata, histori perubahan, serta jejak keputusan yang dapat dijelaskan kembali.

Seluruh data diperlakukan sebagai aset jangka panjang.

Tidak ada data penting yang dirancang untuk bersifat sementara apabila masih memiliki nilai historis.

Database harus mampu:

- menjelaskan asal data;
- menjelaskan proses perubahan data;
- menjelaskan hubungan antarentitas;
- mendukung audit penuh;
- mendukung AI reasoning;
- mendukung knowledge graph;
- mendukung analitik jangka panjang.

---

# Prinsip Perancangan Database

Seluruh skema database NovaNusa mengikuti prinsip berikut.

## Single Source of Truth

Satu fakta hanya boleh memiliki satu representasi utama.

## Explainability

Seluruh data harus dapat ditelusuri sumbernya.

## Traceability

Perubahan data memiliki histori.

## Scalability

Skema harus mampu berkembang tanpa merusak struktur lama.

## Modularity

Domain data dipisahkan secara jelas.

## Extensibility

Penambahan domain baru tidak boleh memerlukan perubahan besar.

## Consistency

Penamaan dan relasi harus seragam.

## Auditability

Aktivitas penting dapat diaudit.

## Security by Design

Data sensitif dipisahkan sesuai tingkat akses.

## AI Readiness

Seluruh struktur data dirancang agar mudah digunakan oleh engine AI.

---

# Karakteristik Data NovaNusa

Data NovaNusa memiliki beberapa karakteristik utama.

## Master Data

Data yang relatif stabil.

Contoh:

- institusi
- supplier
- principal
- kategori
- wilayah
- produk

## Transaction Data

Data yang berubah setiap waktu.

Contoh:

- paket pengadaan
- aktivitas pengguna
- workflow
- approval
- rekomendasi AI

## Historical Data

Data histori yang tidak boleh dihapus.

## Analytical Data

Data agregasi.

## Knowledge Data

Data hasil ekstraksi AI.

## Reference Data

Data referensi nasional.

---

# Kategori Penyimpanan Data

Secara konseptual NovaNusa menggunakan beberapa kelompok penyimpanan data.

## Operational Database

Menyimpan transaksi utama.

## Analytical Database

Menyimpan data agregasi.

## Search Index

Menyimpan indeks pencarian.

## Knowledge Store

Menyimpan knowledge graph.

## Vector Store

Menyimpan embedding AI.

## Object Storage

Menyimpan dokumen.

## Cache Layer

Menyimpan data sementara.

Masing-masing kelompok tersebut memiliki tanggung jawab yang berbeda dan saling melengkapi sebagai satu kesatuan ekosistem data NovaNusa.

---

# Logical Database Landscape

Secara logis database NovaNusa dibagi menjadi beberapa domain besar.

1. Master Data
2. Government Data
3. Supplier Data
4. Product Data
5. Procurement Data
6. Knowledge Data
7. AI Data
8. User Data
9. Workflow Data
10. Analytics Data
11. Notification Data
12. Integration Data
13. Audit Data
14. Security Data

Seluruh domain tersebut saling terhubung melalui identitas yang konsisten dan relasi yang terdokumentasi.

---

# Domain 1 — Master Data

Master Data merupakan fondasi seluruh domain lainnya.

Karakteristik:

- relatif stabil;
- digunakan lintas modul;
- memiliki identifier permanen;
- memiliki lifecycle panjang;
- menjadi referensi utama sistem.

Objek utama pada domain ini meliputi:

- wilayah administratif;
- institusi;
- organisasi;
- supplier;
- principal;
- brand;
- kategori;
- klasifikasi produk;
- satuan;
- referensi nasional;
- kode standar;
- metadata referensi.

Master Data tidak bergantung pada transaksi harian dan menjadi referensi tunggal bagi seluruh proses bisnis.

---

# Domain 2 — Government Data Layer

Government Data Layer merupakan domain yang menyimpan seluruh informasi mengenai institusi pemerintah sebagai objek utama ekosistem NovaNusa.

Domain ini menjadi fondasi utama proses identifikasi kebutuhan, analisis pengadaan, pemetaan institusi, dan pengembangan intelligence.

Karakteristik domain ini:

- bersifat nasional;
- memiliki struktur hierarkis;
- mendukung perubahan organisasi;
- menyimpan histori perubahan;
- dapat digunakan lintas modul;
- menjadi referensi utama AI.

Objek utama meliputi:

- kementerian;
- lembaga;
- pemerintah daerah;
- provinsi;
- kabupaten;
- kota;
- kecamatan;
- desa;
- organisasi perangkat daerah;
- unit kerja;
- rumah sakit;
- sekolah;
- perguruan tinggi;
- badan layanan umum;
- BUMN;
- BUMD;
- institusi vertikal;
- satuan kerja;
- unit pelaksana teknis.

Setiap institusi memiliki identitas permanen sehingga perubahan nama organisasi tidak menghilangkan histori data.

---

# Domain 3 — Supplier Data Layer

Supplier Data Layer menyimpan seluruh informasi mengenai perusahaan penyedia barang dan jasa.

Domain ini tidak hanya menyimpan identitas perusahaan, tetapi juga hubungan bisnis, kompetensi, legalitas, dan histori aktivitas.

Objek utama meliputi:

- supplier;
- principal;
- distributor;
- reseller;
- dealer;
- manufacturer;
- partner;
- agen;
- importir;
- eksportir;
- konsultan;
- kontraktor;
- penyedia layanan.

Informasi yang dikelola meliputi:

- identitas perusahaan;
- legalitas;
- alamat;
- wilayah operasional;
- kategori usaha;
- sertifikasi;
- kontak;
- website;
- media sosial;
- status aktif;
- histori perubahan.

Supplier dapat memiliki hubungan dengan lebih dari satu principal maupun lebih dari satu kategori produk.

---

# Domain 4 — Product Data Layer

Product Data Layer menyimpan seluruh informasi mengenai produk yang dapat dipetakan terhadap kebutuhan pemerintah.

Domain ini merupakan inti proses product matching.

Karakteristik:

- mendukung jutaan produk;
- mendukung multi-brand;
- mendukung multi-principal;
- mendukung klasifikasi bertingkat;
- mendukung pencarian semantik.

Objek utama:

- produk;
- brand;
- kategori;
- subkategori;
- spesifikasi;
- atribut;
- varian;
- tipe;
- model;
- SKU;
- nomor katalog;
- dokumen produk;
- gambar;
- sertifikasi;
- kompatibilitas.

Setiap produk dapat memiliki lebih dari satu atribut spesifikasi tanpa mengubah struktur dasar database.

---

# Domain 5 — Procurement Data Layer

Procurement Data Layer merupakan domain transaksi terbesar di NovaNusa.

Domain ini menyimpan seluruh informasi mengenai kebutuhan pengadaan pemerintah.

Objek utama:

- paket pengadaan;
- RUP;
- kontrak;
- tender;
- e-purchasing;
- e-katalog;
- penyedia;
- nilai pagu;
- nilai kontrak;
- jadwal;
- status;
- sumber pendanaan;
- metode pengadaan.

Data pengadaan bersifat historis.

Setiap perubahan status wajib tercatat sehingga seluruh siklus pengadaan dapat direkonstruksi kembali.

Domain ini menjadi sumber utama proses analitik dan AI recommendation.

---

# Hubungan Antar Domain

Secara konseptual hubungan antar domain utama adalah sebagai berikut.

Government Data
        │
        │
        ▼
Procurement Data
        │
        │
        ├─────────────► Product Data
        │
        ├─────────────► Supplier Data
        │
        ▼
Knowledge Layer
        │
        ▼
AI Layer

Hubungan tersebut memastikan bahwa seluruh rekomendasi AI selalu dapat ditelusuri kembali hingga sumber data awal.

---

# Prinsip Integritas Data

Seluruh domain wajib menjaga integritas melalui prinsip berikut:

- tidak ada identitas ganda;
- tidak ada referensi yatim (orphan reference);
- setiap relasi memiliki pemilik yang jelas;
- setiap perubahan memiliki histori;
- setiap objek memiliki lifecycle;
- setiap objek memiliki metadata;
- setiap objek memiliki status yang terdokumentasi.

Integritas data menjadi tanggung jawab seluruh domain, bukan hanya database.


---

# Domain 6 — Knowledge Data Layer

Knowledge Data Layer merupakan pembeda utama NovaNusa dibandingkan sistem informasi pengadaan konvensional.

Domain ini tidak hanya menyimpan data mentah, tetapi juga hasil interpretasi, hubungan antarentitas, insight, serta pengetahuan yang dihasilkan melalui proses analisis.

Knowledge disusun sebagai aset jangka panjang yang terus berkembang seiring bertambahnya data.

Objek utama meliputi:

- knowledge entity;
- knowledge relationship;
- concept;
- taxonomy;
- ontology;
- business rule;
- semantic tag;
- keyword;
- topic;
- evidence;
- confidence score;
- reasoning chain;
- explanation.

Knowledge dapat berasal dari:

- data pemerintah;
- data supplier;
- data produk;
- dokumen;
- hasil ekstraksi AI;
- validasi manusia.

Setiap knowledge memiliki sumber yang jelas sehingga seluruh rekomendasi dapat dijelaskan kembali.

---

# Domain 7 — AI Data Layer

AI Data Layer menyimpan seluruh informasi yang diperlukan untuk mendukung kemampuan kecerdasan buatan NovaNusa.

Domain ini tidak menyimpan model AI, tetapi metadata yang berkaitan dengan proses AI.

Objek utama meliputi:

- AI session;
- prompt;
- response;
- embedding;
- inference metadata;
- confidence;
- model version;
- evaluation;
- feedback;
- recommendation;
- explanation;
- reasoning trace.

Seluruh aktivitas AI wajib memiliki hubungan dengan sumber data yang digunakan.

Dengan demikian seluruh keputusan AI dapat diaudit.

---

# Domain 8 — User Data Layer

User Data Layer menyimpan informasi seluruh pengguna sistem.

Karakteristik:

- mendukung multi-organisasi;
- mendukung multi-role;
- mendukung delegasi kewenangan;
- mendukung audit keamanan.

Objek utama meliputi:

- pengguna;
- organisasi;
- jabatan;
- peran;
- hak akses;
- grup;
- preferensi;
- profil;
- autentikasi;
- otorisasi.

Identitas pengguna bersifat permanen sehingga histori aktivitas tetap terjaga walaupun terjadi perubahan organisasi.

---

# Domain 9 — Workflow Data Layer

Workflow Data Layer mengelola seluruh proses bisnis NovaNusa.

Workflow didefinisikan sebagai rangkaian aktivitas yang memiliki status, pelaksana, waktu, dan hasil.

Objek utama meliputi:

- workflow;
- task;
- assignment;
- approval;
- review;
- escalation;
- milestone;
- status;
- SLA;
- aktivitas;
- komentar;
- lampiran.

Workflow dirancang independen terhadap domain tertentu sehingga dapat digunakan kembali oleh berbagai modul.

---

# Domain 10 — Analytics Data Layer

Analytics Data Layer menyimpan data yang telah diproses untuk kebutuhan analitik.

Karakteristik:

- tidak menggantikan data operasional;
- berorientasi agregasi;
- mendukung dashboard;
- mendukung pelaporan nasional;
- mendukung business intelligence.

Objek utama:

- indikator;
- metrik;
- agregasi;
- statistik;
- tren;
- peringkat;
- distribusi;
- forecasting;
- benchmark;
- KPI.

Analytics menggunakan data operasional sebagai sumber utama, namun dipisahkan agar tidak mengganggu transaksi harian.

---

# Domain 11 — Notification Data Layer

Notification Data Layer mengelola seluruh komunikasi sistem.

Objek utama:

- notifikasi;
- template;
- kanal;
- penerima;
- jadwal;
- status pengiriman;
- histori;
- prioritas.

Sistem mendukung berbagai media komunikasi tanpa mengubah struktur dasar domain.

---

# Domain 12 — Integration Data Layer

Integration Data Layer menyimpan metadata seluruh integrasi eksternal.

Objek utama:

- external system;
- endpoint;
- connector;
- credential reference;
- synchronization;
- schedule;
- mapping;
- transform rule;
- integration log;
- retry policy.

Domain ini memastikan setiap integrasi memiliki dokumentasi dan histori yang lengkap.


---

# Domain 13 — Audit Data Layer

Audit Data Layer menyimpan seluruh jejak aktivitas penting di dalam NovaNusa.

Audit tidak hanya mencatat perubahan data, tetapi juga konteks perubahan, pelaku, waktu, sumber, dan alasan perubahan apabila tersedia.

Objek utama:

- audit log;
- data change log;
- access log;
- user activity log;
- API activity log;
- AI activity log;
- workflow activity log;
- integration log;
- security event;
- approval history.

Audit Data Layer wajib bersifat append-only secara konseptual.

Data audit tidak boleh diubah untuk kepentingan operasional biasa.

---

# Domain 14 — Security Data Layer

Security Data Layer menyimpan metadata keamanan sistem.

Objek utama:

- role;
- permission;
- policy;
- access scope;
- session;
- authentication method;
- authorization rule;
- token metadata;
- security event;
- risk flag;
- blocked entity.

Security Data Layer berfungsi memastikan bahwa setiap akses terhadap data dan fitur dapat dikendalikan, ditelusuri, dan diaudit.

---

# Relationship Matrix

Relationship Matrix mendefinisikan hubungan konseptual antarentitas utama NovaNusa.

| Entitas Utama | Terhubung Dengan | Jenis Hubungan |
|---|---|---|
| Institution | Procurement Package | One-to-Many |
| Institution | Contact | One-to-Many |
| Institution | Region | Many-to-One |
| Procurement Package | Product Category | Many-to-Many |
| Procurement Package | Supplier | Many-to-Many |
| Procurement Package | AI Recommendation | One-to-Many |
| Supplier | Product | Many-to-Many |
| Supplier | Principal | Many-to-Many |
| Product | Product Category | Many-to-One |
| Product | Brand | Many-to-One |
| User | Organization | Many-to-One |
| User | Role | Many-to-Many |
| Workflow | Task | One-to-Many |
| Task | User | Many-to-One |
| AI Recommendation | Evidence | One-to-Many |
| Knowledge Entity | Knowledge Relationship | One-to-Many |
| External System | Integration Log | One-to-Many |
| User | Audit Log | One-to-Many |

Relationship Matrix ini menjadi acuan awal bagi seluruh logical dan physical database design.

---

# Data Ownership

Setiap kelompok data wajib memiliki pemilik konseptual.

| Domain Data | Pemilik Konseptual |
|---|---|
| Master Data | Platform Core |
| Government Data | Government Intelligence Module |
| Supplier Data | Supplier Intelligence Module |
| Product Data | Product Intelligence Module |
| Procurement Data | Procurement Intelligence Module |
| Knowledge Data | Knowledge Engine |
| AI Data | AI Engine |
| User Data | Identity and Access Module |
| Workflow Data | Workflow Engine |
| Analytics Data | Analytics Module |
| Notification Data | Communication Module |
| Integration Data | Integration Module |
| Audit Data | Audit and Compliance Module |
| Security Data | Security Module |

Pemilik konseptual bertanggung jawab menjaga kualitas, konsistensi, dan lifecycle data.

---

# Primary Identifier Standard

Setiap entitas utama wajib memiliki identifier permanen.

Prinsip identifier:

- unik;
- tidak berubah;
- tidak bergantung pada nama;
- tidak bergantung pada lokasi;
- tidak bergantung pada status;
- dapat digunakan lintas modul;
- dapat digunakan untuk audit.

Identifier tidak boleh diganti hanya karena nama institusi, nama produk, atau struktur organisasi berubah.

---

# Naming Convention

Penamaan skema database wajib konsisten.

Prinsip penamaan:

- menggunakan bahasa Inggris untuk nama teknis;
- menggunakan bentuk singular untuk entitas konseptual;
- menggunakan bentuk jelas dan tidak ambigu;
- tidak menggunakan singkatan yang tidak umum;
- tidak mencampur bahasa teknis;
- tidak menggunakan nama yang terlalu umum seperti data, info, atau item tanpa konteks.

Contoh nama konseptual:

- institution
- procurement_package
- supplier
- product
- product_category
- ai_recommendation
- knowledge_entity
- workflow_task
- audit_log

---

# Standard Field Groups

Setiap entitas utama secara konseptual memiliki kelompok field berikut.

## Identity Fields

- id;
- external_id;
- source_id;
- canonical_name.

## Descriptive Fields

- name;
- description;
- type;
- category;
- status.

## Source Fields

- source_system;
- source_url;
- source_document;
- source_timestamp;
- ingestion_batch_id.

## Lifecycle Fields

- created_at;
- created_by;
- updated_at;
- updated_by;
- deleted_at;
- deleted_by.

## Audit Fields

- version;
- change_reason;
- confidence_score;
- validation_status;
- review_status.

Tidak semua entitas harus memiliki seluruh field, tetapi seluruh entitas utama wajib mengikuti pola standar ini.

---

# Soft Delete Strategy

NovaNusa menggunakan prinsip soft delete untuk data penting.

Data tidak langsung dihapus apabila masih memiliki nilai historis, audit, atau analitik.

Soft delete digunakan untuk:

- institusi;
- supplier;
- produk;
- kontak;
- workflow;
- rekomendasi;
- knowledge;
- user;
- integrasi.

Hard delete hanya boleh digunakan untuk:

- cache;
- data sementara;
- data duplikat sebelum validasi;
- data yang diwajibkan untuk dihapus karena alasan legal.

---

# Versioning Strategy

Entitas penting wajib mendukung versioning.

Versioning digunakan untuk menjaga histori perubahan.

Entitas yang wajib memiliki versi:

- institution;
- supplier;
- product;
- procurement package;
- AI recommendation;
- knowledge entity;
- workflow;
- policy;
- document metadata.

Setiap versi baru harus dapat ditelusuri ke versi sebelumnya.

---

# Historical Data Strategy

NovaNusa tidak boleh kehilangan konteks historis.

Data historis disimpan untuk:

- analisis tren;
- audit;
- explainability;
- forecasting;
- pembelajaran AI;
- evaluasi kebijakan;
- pelaporan.

Histori disimpan dalam bentuk:

- version record;
- change log;
- event log;
- snapshot;
- time-series aggregate.

---

# Partition Strategy

Partition secara konseptual digunakan untuk data berskala besar.

Kandidat data yang dapat dipartisi:

- procurement package;
- audit log;
- API log;
- AI inference log;
- notification log;
- integration log;
- analytics aggregate;
- search event.

Strategi partition dapat berbasis:

- waktu;
- wilayah;
- sumber data;
- domain;
- status.

Pemilihan strategi partition wajib mempertimbangkan pola akses data.

---

# Index Strategy

Index digunakan untuk mempercepat pencarian dan relasi.

Kandidat index utama:

- identifier;
- external_id;
- canonical_name;
- institution_id;
- supplier_id;
- product_id;
- procurement_package_id;
- region_id;
- status;
- category;
- source_system;
- created_at;
- updated_at;
- confidence_score.

Index tidak boleh dibuat tanpa memahami pola akses.

Index harus mendukung API, analytics, search, dan AI retrieval.

---

# Archiving Strategy

Data lama tidak otomatis dihapus.

Data dapat dipindahkan ke archive apabila:

- jarang diakses;
- tidak lagi digunakan untuk operasi harian;
- tetap diperlukan untuk audit;
- tetap diperlukan untuk analitik historis.

Archive wajib tetap dapat ditelusuri dari data utama.

---

# Data Quality Rules

Setiap data wajib melalui aturan kualitas.

Dimensi kualitas:

- completeness;
- accuracy;
- consistency;
- validity;
- uniqueness;
- timeliness;
- traceability;
- explainability.

Contoh aturan:

- institusi wajib memiliki nama;
- supplier wajib memiliki identitas legal apabila tersedia;
- produk wajib memiliki kategori;
- paket pengadaan wajib memiliki sumber data;
- rekomendasi AI wajib memiliki evidence;
- kontak wajib memiliki status validasi;
- knowledge wajib memiliki confidence score.

---

# Integrity Rules

Integrity Rules memastikan hubungan data tetap sehat.

Aturan utama:

- setiap procurement package wajib terhubung ke institution;
- setiap product wajib memiliki category;
- setiap AI recommendation wajib memiliki evidence;
- setiap workflow task wajib memiliki status;
- setiap audit log wajib memiliki timestamp;
- setiap integration log wajib memiliki source system;
- setiap user activity wajib memiliki user atau system actor;
- setiap knowledge relationship wajib memiliki source dan target.

Data tanpa relasi yang jelas wajib masuk proses review.

---

# Data Lifecycle

Lifecycle data NovaNusa terdiri dari:

1. Created
2. Ingested
3. Normalized
4. Validated
5. Enriched
6. Linked
7. Used
8. Reviewed
9. Archived
10. Retired

Tidak semua data melalui seluruh tahap, tetapi setiap domain wajib mendefinisikan lifecycle masing-masing.

---

# Validation Status Standard

Status validasi standar:

- unvalidated;
- auto_validated;
- human_review_required;
- human_validated;
- rejected;
- deprecated.

Status ini digunakan lintas domain agar proses review konsisten.

---

# Confidence Score Standard

Confidence score digunakan untuk data hasil ekstraksi, pencocokan, enrichment, dan AI.

Rentang konseptual:

- 0.00 sampai 1.00.

Interpretasi umum:

- 0.00 - 0.39: rendah;
- 0.40 - 0.69: sedang;
- 0.70 - 0.89: tinggi;
- 0.90 - 1.00: sangat tinggi.

Confidence score tidak menggantikan validasi manusia pada keputusan penting.

---

# Source Traceability

Setiap data yang berasal dari luar sistem wajib menyimpan informasi sumber.

Minimal metadata sumber:

- source_system;
- source_name;
- source_url;
- source_reference_id;
- source_timestamp;
- ingestion_time;
- ingestion_batch_id.

Traceability wajib tersedia untuk seluruh data pemerintah, produk, supplier, dan rekomendasi AI.

---

# AI Explainability Requirement

Setiap rekomendasi AI wajib memiliki:

- input data reference;
- evidence;
- reasoning summary;
- confidence score;
- model metadata;
- generated timestamp;
- review status.

AI tidak boleh menghasilkan rekomendasi penting tanpa bukti yang dapat ditelusuri.

---

# Search Readiness

Skema data harus mendukung pencarian:

- berdasarkan nama;
- berdasarkan kategori;
- berdasarkan wilayah;
- berdasarkan institusi;
- berdasarkan supplier;
- berdasarkan produk;
- berdasarkan kebutuhan;
- berdasarkan dokumen;
- berdasarkan konteks semantik.

Setiap entitas utama harus dapat diindeks ke search layer.

---

# Vector Readiness

Data tekstual penting harus dapat diubah menjadi embedding.

Kandidat embedding:

- nama paket pengadaan;
- deskripsi kebutuhan;
- spesifikasi produk;
- profil supplier;
- dokumen produk;
- knowledge entity;
- reasoning summary;
- catatan review.

Embedding wajib tetap terhubung dengan data sumber.

---

# Graph Readiness

NovaNusa harus mendukung representasi graph.

Node utama:

- institution;
- supplier;
- principal;
- product;
- category;
- procurement package;
- region;
- knowledge entity;
- user;
- workflow.

Edge utama:

- owns;
- buys;
- supplies;
- represents;
- belongs_to;
- matches;
- recommends;
- reviewed_by;
- located_in;
- related_to.

Graph digunakan untuk intelligence, discovery, dan explainability.

---

# Privacy and Sensitive Data

Data sensitif wajib dipisahkan secara konseptual.

Kategori data sensitif:

- credential;
- token;
- personal contact;
- user authentication;
- security event;
- internal note;
- confidential business data.

Data sensitif wajib memiliki akses terbatas dan audit khusus.

---

# Future Expansion

Database Schema NovaNusa harus siap diperluas untuk:

- sektor pendidikan;
- sektor kesehatan;
- sektor infrastruktur;
- sektor energi;
- sektor transportasi;
- sektor pangan;
- sektor ekspor;
- sektor investasi;
- sektor UMKM;
- sektor riset;
- sektor kebijakan publik;
- sektor internasional.

Penambahan sektor baru tidak boleh merusak struktur domain inti.

---

# Batasan Dokumen Ini

Dokumen ini tidak membahas:

- SQL DDL;
- migration script;
- teknologi database spesifik;
- ukuran server;
- konfigurasi index fisik;
- konfigurasi backup teknis;
- implementasi ORM;
- query optimization teknis;
- kode aplikasi.

Seluruh hal tersebut akan dibahas pada dokumen implementasi terpisah.

---

# Kesimpulan

Database Schema NovaNusa dirancang sebagai fondasi permanen untuk membangun platform intelligence yang konsisten, dapat diaudit, dapat dijelaskan, dan siap berkembang.

Skema ini menjaga agar seluruh data utama NovaNusa memiliki struktur, relasi, lifecycle, kualitas, dan kepemilikan yang jelas.

Dengan database schema yang kuat, NovaNusa dapat berkembang dari sistem procurement intelligence menjadi platform intelligence nasional yang mampu menghubungkan data pemerintah, supplier, produk, AI, workflow, dan knowledge secara terpadu.

Seluruh pengembangan database NovaNusa wajib mengacu pada dokumen ini.

---

**Status Dokumen:** FINAL
