# 13 — NOVANUSA PLATFORM SERVICES ARCHITECTURE

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan permanen mengenai arsitektur Platform Services NovaNusa.

Platform Services adalah kumpulan layanan lintas domain yang menyediakan kapabilitas bersama bagi seluruh sistem NovaNusa.

Dokumen ini memastikan seluruh layanan bersama dirancang secara konsisten, governed, reusable, observable, auditable, secure, dan siap berkembang secara enterprise-grade.

---

# Tujuan Dokumen

Platform Services Architecture bertujuan untuk:

- mendefinisikan layanan bersama NovaNusa
- menghindari duplikasi kapabilitas antar domain
- menyediakan fondasi reusable untuk seluruh aplikasi
- menjaga konsistensi governance lintas sistem
- mendukung skalabilitas platform
- memperkuat auditability dan observability
- mendukung AI-assisted platform operation
- memastikan layanan inti dapat dikembangkan tanpa merusak domain bisnis

---

# Ruang Lingkup

Dokumen ini mencakup:

- Platform Services Philosophy
- Shared Service Principles
- Service Ownership
- Identity Service
- Access Control Service
- User & Organization Service
- Configuration Service
- Notification Service
- Search Service
- Document Service
- File Service
- Audit Service
- Scheduler Service
- Workflow Support Service
- AI Gateway Service
- Knowledge Service
- Observability Service
- Reporting Service
- Integration Support Service
- Governance Service
- Future Platform Readiness

Dokumen ini tidak membahas implementasi teknis spesifik.

---

# Platform Services Philosophy

NovaNusa memandang Platform Services sebagai fondasi bersama yang memungkinkan seluruh domain bekerja secara konsisten.

Platform Services bukan sekadar layanan utilitas.

Platform Services adalah lapisan strategis yang menjaga keseragaman identitas, keamanan, konfigurasi, audit, notifikasi, pencarian, dokumen, observability, knowledge, dan AI gateway di seluruh platform.

Tanpa Platform Services, setiap domain berisiko membangun mekanisme sendiri, menyebabkan duplikasi, inkonsistensi, dan lemahnya governance.

---

# Prinsip Dasar Platform Services

Seluruh Platform Services wajib mengikuti prinsip berikut.

## Reusable

Layanan harus dapat digunakan oleh lebih dari satu domain.

---

## Governed

Layanan berada di bawah tata kelola platform.

---

## Secure by Design

Keamanan melekat sejak awal desain layanan.

---

## Observable

Kondisi layanan harus dapat diamati.

---

## Auditable

Aktivitas penting harus dapat ditelusuri.

---

## Consistent

Perilaku layanan harus konsisten di seluruh domain.

---

## Extensible

Layanan harus dapat diperluas tanpa memecah kontrak utama.

---

## Domain Neutral

Platform Services tidak boleh memihak domain tertentu.

Layanan harus mendukung seluruh domain secara adil dan konsisten.

---

# Posisi Platform Services dalam Arsitektur NovaNusa

Platform Services berada di antara lapisan aplikasi dan domain business intelligence.

Secara konseptual:

User Interface

↓

Application Layer

↓

Platform Services

↓

Domain Services

↓

Data & Knowledge Layer

↓

External Integration

Platform Services menyediakan kapabilitas bersama yang dipakai oleh seluruh domain tanpa mengambil alih tanggung jawab domain.

---

# Kategori Platform Services

Platform Services NovaNusa dikategorikan menjadi beberapa kelompok besar.

## Core Governance Services

Layanan yang mengatur identitas, akses, audit, konfigurasi, dan kepatuhan.

## Operational Services

Layanan yang mendukung operasi sistem seperti scheduler, notification, observability, dan reporting.

## Intelligence Support Services

Layanan yang mendukung AI, knowledge, search, dan analytics.

## Content & Document Services

Layanan yang mengelola file, dokumen, template, attachment, dan artefak informasi.

## Integration Support Services

Layanan yang mendukung komunikasi lintas sistem dan integrasi eksternal.

---

# Service Ownership

Setiap Platform Service harus memiliki pemilik yang jelas.

Ownership mencakup:

- tanggung jawab layanan
- standar kualitas
- SLA
- governance
- perubahan kontrak
- evaluasi risiko
- dokumentasi
- lifecycle layanan

Tidak diperbolehkan terdapat Platform Service tanpa ownership.

---

# Service Contract

Setiap Platform Service harus memiliki kontrak layanan.

Kontrak layanan mendefinisikan:

- tujuan layanan
- kapabilitas utama
- input
- output
- error condition
- security rule
- audit rule
- SLA
- dependency
- limitation

Kontrak layanan harus stabil dan terdokumentasi.

---

# Service Boundary

Setiap Platform Service memiliki batas tanggung jawab.

Boundary memastikan layanan tidak berubah menjadi domain bisnis.

Platform Service hanya menyediakan kapabilitas bersama, sedangkan keputusan bisnis tetap berada pada domain masing-masing.

---

# Service Lifecycle

Lifecycle Platform Service meliputi:

Proposed

↓

Defined

↓

Approved

↓

Published

↓

Operational

↓

Monitored

↓

Improved

↓

Deprecated

↓

Retired

Setiap perubahan lifecycle harus terdokumentasi.

---

# Service Dependency

Platform Services dapat saling bergantung, namun dependency harus dikendalikan.

Dependency wajib:

- jelas
- terdokumentasi
- tidak siklik
- memiliki fallback
- memiliki observability
- memiliki strategi recovery

Dependency yang tidak terkendali dapat melemahkan stabilitas platform.

---

# Identity Service

Identity Service menyediakan fondasi identitas pengguna, organisasi, sistem, dan aktor non-manusia.

Identity Service bertanggung jawab terhadap:

- identitas pengguna
- identitas organisasi
- identitas sistem
- identitas service account
- identitas AI agent
- identitas integration actor

Setiap aktivitas penting dalam NovaNusa harus memiliki identity reference yang jelas.

---

# Identity Principles

Identity Service wajib memenuhi prinsip berikut.

- unique
- verifiable
- auditable
- secure
- lifecycle-managed
- organization-aware

Identitas tidak boleh diperlakukan sebagai teks bebas.

Identitas harus menjadi objek resmi dalam platform.

---

# User Service

User Service mengelola profil pengguna platform.

User Service mencakup:

- user profile
- role association
- organization association
- permission context
- activity context
- preference dasar
- status pengguna

User Service tidak mengambil keputusan bisnis, tetapi menyediakan konteks pengguna bagi domain lain.

---

# Organization Service

Organization Service mengelola struktur organisasi yang menggunakan NovaNusa.

Organization dapat merepresentasikan:

- internal company
- business unit
- client organization
- supplier organization
- institution
- partner
- external stakeholder

Organization Service menjadi referensi lintas domain agar struktur organisasi konsisten.

---

# Access Control Service

Access Control Service mengatur hak akses pengguna, sistem, dan aktor lain.

Access Control Service memastikan setiap tindakan hanya dilakukan oleh pihak yang memiliki kewenangan.

Access control wajib berlaku pada:

- data
- workflow
- approval
- document
- AI output
- report
- configuration
- integration

---

# Access Control Principles

Access Control wajib mengikuti prinsip:

- least privilege
- need to know
- role awareness
- organization awareness
- auditability
- separation of duties
- revocability

Hak akses tidak boleh bersifat permanen tanpa evaluasi.


# Configuration Service

Configuration Service menyediakan mekanisme terpusat untuk mengelola konfigurasi platform.

Konfigurasi mencakup:

- parameter sistem
- pengaturan domain
- feature flag
- AI policy
- workflow policy
- notification policy
- integration policy
- security policy

Configuration harus dipisahkan dari logika bisnis.

---

# Configuration Principles

Seluruh konfigurasi harus:

- terdokumentasi
- memiliki versi
- dapat diaudit
- memiliki pemilik
- dapat divalidasi
- dapat dipulihkan
- memiliki histori perubahan

Perubahan konfigurasi merupakan aktivitas governance.

---

# Notification Service

Notification Service menyediakan mekanisme komunikasi resmi kepada pengguna maupun sistem.

Notification dapat digunakan untuk:

- informasi
- pengingat
- approval
- exception
- SLA warning
- workflow update
- AI recommendation ready
- integration status

Notification bukan sumber kebenaran utama, tetapi media penyampaian informasi.

---

# Notification Channels

Platform mendukung berbagai kanal komunikasi secara konseptual.

Contoh:

- Email
- SMS
- Push Notification
- In-App Notification
- Collaboration Platform
- Webhook
- Future Channels

Penambahan kanal baru tidak boleh mengubah kontrak layanan Notification.

---

# Search Service

Search Service menyediakan kemampuan pencarian terpadu pada seluruh platform.

Search dapat digunakan terhadap:

- institution
- supplier
- product
- opportunity
- knowledge
- workflow
- document
- report
- AI artifact

Search Service bertanggung jawab terhadap pengalaman pencarian yang konsisten.

---

# Search Principles

Search harus mampu mendukung:

- structured search
- semantic search
- hybrid search
- contextual search
- filtered search
- ranked search

Seluruh hasil pencarian harus dapat dijelaskan asal-usulnya.

---

# Document Service

Document Service mengelola seluruh dokumen yang menjadi bagian dari proses bisnis.

Document meliputi:

- proposal
- quotation
- contract
- report
- attachment
- AI report
- workflow document
- approval document

Document memiliki lifecycle tersendiri namun tetap mengikuti governance platform.

---

# Document Principles

Setiap dokumen harus:

- memiliki identitas
- memiliki versi
- memiliki pemilik
- memiliki klasifikasi
- memiliki histori
- dapat diaudit
- memiliki kebijakan retensi

---

# File Service

File Service menyediakan pengelolaan berkas digital yang digunakan oleh platform.

Contoh:

- gambar
- PDF
- spreadsheet
- presentasi
- arsip
- media
- dataset

File Service bertanggung jawab terhadap metadata dan integritas berkas.

---

# File Lifecycle

Lifecycle file meliputi:

Uploaded

↓

Validated

↓

Classified

↓

Referenced

↓

Used

↓

Archived

↓

Retired

Setiap file harus dapat ditelusuri sepanjang lifecycle tersebut.

---

# Audit Service

Audit Service menyediakan pencatatan resmi terhadap aktivitas penting platform.

Audit mencakup:

- login
- perubahan data
- approval
- perubahan workflow
- perubahan konfigurasi
- penggunaan AI
- perubahan akses
- integrasi eksternal

Audit Service menjadi sumber utama untuk investigasi dan kepatuhan.

---

# Audit Principles

Audit wajib memenuhi prinsip berikut.

- immutable
- traceable
- timestamped
- actor-aware
- correlation-aware
- secure
- retained

Audit tidak boleh digunakan sebagai media perubahan data.

---

# Scheduler Service

Scheduler Service mengelola aktivitas yang dipicu oleh waktu maupun jadwal.

Scheduler mendukung:

- pekerjaan berkala
- sinkronisasi
- housekeeping
- evaluasi AI
- pembaruan knowledge
- monitoring
- pelaporan

Scheduler hanya memicu workflow yang telah didefinisikan.

---

# Scheduler Principles

Scheduler harus:

- dapat diamati
- dapat diaudit
- mendukung retry
- mendukung timeout
- mendukung recovery
- mendukung prioritas

---

# Workflow Support Service

Workflow Support Service menyediakan layanan bersama yang membantu Workflow Architecture.

Kapabilitas meliputi:

- workflow registry
- workflow lookup
- workflow metadata
- workflow correlation
- workflow tracking
- workflow reference

Layanan ini tidak menjalankan workflow, tetapi menyediakan informasi yang diperlukan oleh workflow engine maupun domain.

---

# Template Service

Template Service menyediakan artefak standar yang dapat digunakan kembali oleh seluruh domain.

Template dapat berupa:

- dokumen
- email
- notifikasi
- laporan
- prompt AI
- formulir
- kontrak
- presentasi

Penggunaan template menjaga konsistensi komunikasi di seluruh platform.

---

# Metadata Service

Metadata Service mengelola informasi deskriptif terhadap seluruh objek platform.

Metadata digunakan untuk:

- klasifikasi
- pencarian
- hubungan antar entitas
- governance
- analitik
- lineage

Metadata tidak menggantikan data utama, tetapi memperkaya konteksnya.

---

# Reference Data Service

Reference Data Service menyediakan data acuan yang digunakan lintas domain.

Contoh:

- kategori
- wilayah
- sektor
- klasifikasi produk
- klasifikasi institusi
- status
- tipe dokumen
- tipe workflow

Reference Data harus memiliki definisi tunggal agar seluruh domain menggunakan terminologi yang sama.


# AI Gateway Service

AI Gateway Service merupakan pintu masuk tunggal bagi seluruh kemampuan Artificial Intelligence yang digunakan dalam platform NovaNusa.

Seluruh domain berinteraksi dengan AI melalui AI Gateway sehingga tata kelola, keamanan, audit, dan observability tetap konsisten.

AI Gateway menyediakan abstraksi terhadap berbagai penyedia maupun jenis model Artificial Intelligence tanpa mengubah kontrak layanan yang digunakan oleh domain.

---

# AI Gateway Responsibilities

AI Gateway bertanggung jawab terhadap:

- AI request routing
- model selection
- policy enforcement
- prompt governance
- response validation
- AI audit
- AI usage tracking
- safety policy
- AI capability registry

AI Gateway tidak mengambil keputusan bisnis.

Keputusan bisnis tetap menjadi tanggung jawab domain masing-masing.

---

# AI Gateway Principles

AI Gateway wajib memenuhi prinsip berikut.

- provider independent
- model independent
- explainable
- observable
- auditable
- secure
- extensible

Perubahan model AI tidak boleh memengaruhi kontrak layanan platform.

---

# Knowledge Service

Knowledge Service mengelola seluruh pengetahuan yang menjadi aset strategis NovaNusa.

Knowledge dapat berasal dari:

- data internal
- hasil AI
- pengalaman pengguna
- workflow
- dokumen
- hubungan antar entitas
- referensi eksternal
- kebijakan organisasi

Knowledge diperlakukan sebagai aset yang terus berkembang.

---

# Knowledge Responsibilities

Knowledge Service bertanggung jawab terhadap:

- knowledge acquisition
- knowledge validation
- knowledge normalization
- knowledge relationship
- knowledge versioning
- knowledge publication
- knowledge lifecycle
- knowledge governance

---

# Knowledge Principles

Knowledge harus:

- reusable
- traceable
- explainable
- versioned
- governed
- searchable
- continuously enriched

Knowledge tidak boleh menjadi kumpulan informasi yang tidak memiliki konteks.

---

# Observability Service

Observability Service menyediakan kemampuan untuk memahami kondisi platform secara menyeluruh.

Observability mencakup:

- service health
- workflow visibility
- platform status
- dependency visibility
- AI usage visibility
- operational insight
- business insight

Observability bukan hanya untuk operasional teknis tetapi juga mendukung evaluasi proses bisnis.

---

# Observability Principles

Observability harus mampu menjawab pertanyaan berikut.

- Apa yang sedang terjadi?
- Mengapa hal tersebut terjadi?
- Di mana masalah terjadi?
- Apa dampaknya?
- Bagaimana status pemulihannya?

Seluruh layanan platform harus dapat diamati secara konsisten.

---

# Reporting Service

Reporting Service menyediakan mekanisme penyusunan laporan berdasarkan data yang telah divalidasi.

Reporting digunakan untuk:

- laporan operasional
- laporan manajemen
- laporan analitik
- laporan AI
- laporan audit
- laporan workflow
- laporan kepatuhan

Reporting tidak menjadi sumber data utama, melainkan representasi informasi yang telah diproses.

---

# Reporting Principles

Setiap laporan harus:

- memiliki sumber yang jelas
- dapat ditelusuri
- memiliki periode
- memiliki identitas
- memiliki versi apabila diperlukan
- dapat direproduksi

---

# Integration Support Service

Integration Support Service menyediakan kapabilitas umum untuk komunikasi dengan sistem eksternal.

Kapabilitas meliputi:

- endpoint registry
- integration policy
- protocol abstraction
- message transformation
- validation support
- integration audit
- integration monitoring

Service ini memastikan integrasi dilakukan secara konsisten di seluruh platform.

---

# Integration Principles

Seluruh integrasi harus:

- secure
- observable
- auditable
- versioned
- loosely coupled
- resilient

Integrasi tidak boleh menciptakan ketergantungan langsung antar domain.

---

# Event Service

Event Service menyediakan mekanisme konseptual untuk pertukaran event di dalam platform.

Event digunakan untuk menyampaikan perubahan yang memiliki makna bisnis.

Contoh event meliputi:

- Opportunity Created
- Product Updated
- Supplier Verified
- Knowledge Published
- Workflow Completed
- AI Recommendation Generated

Event menjadi media komunikasi utama antar layanan tanpa menciptakan hubungan yang erat.

---

# Event Principles

Event harus:

- immutable
- timestamped
- uniquely identified
- correlated
- traceable
- meaningful

Setiap event harus merepresentasikan fakta yang telah terjadi.

---

# Messaging Service

Messaging Service menyediakan mekanisme komunikasi asinkron antar layanan.

Messaging mendukung:

- koordinasi workflow
- sinkronisasi proses
- pemberitahuan internal
- pemrosesan bertahap
- distribusi pekerjaan

Messaging merupakan layanan pendukung, bukan domain bisnis.

---

# Platform Registry

Platform Registry menyediakan katalog resmi terhadap seluruh layanan bersama yang tersedia dalam NovaNusa.

Registry mendokumentasikan:

- identitas layanan
- tujuan layanan
- kontrak layanan
- status layanan
- ownership
- dependency
- lifecycle

Registry menjadi referensi utama bagi seluruh domain.

---

# Shared Intelligence Services

NovaNusa menyediakan sekumpulan layanan intelligence yang dapat digunakan lintas domain.

Contoh layanan meliputi:

- semantic understanding
- recommendation support
- entity relationship analysis
- document understanding
- similarity analysis
- knowledge enrichment
- classification support
- summarization support

Shared Intelligence Services mempercepat pengembangan domain tanpa menduplikasi kemampuan AI.

---

# Platform Service Collaboration

Platform Services dirancang untuk saling melengkapi.

Sebagai contoh:

Identity Service menyediakan konteks pengguna.

↓

Access Control Service menentukan kewenangan.

↓

Workflow memanfaatkan Configuration Service.

↓

AI Gateway menghasilkan rekomendasi.

↓

Knowledge Service memperkaya informasi.

↓

Audit Service mencatat aktivitas.

↓

Observability Service memantau proses.

↓

Reporting Service menyajikan hasil.

Kolaborasi tersebut membentuk fondasi bersama yang digunakan oleh seluruh domain NovaNusa secara konsisten.


# Platform Governance

Platform Services berada di bawah tata kelola platform secara menyeluruh.

Governance memastikan bahwa seluruh layanan bersama:

- memiliki tujuan yang jelas
- memiliki kontrak yang terdokumentasi
- memiliki pemilik
- memenuhi standar keamanan
- memenuhi standar observability
- memenuhi standar audit
- mengikuti lifecycle yang ditetapkan

Governance memastikan Platform Services berkembang secara terkendali dan konsisten.

---

# Service Governance Principles

Setiap Platform Service wajib:

- memiliki definisi resmi
- memiliki dokumentasi
- memiliki ownership
- memiliki SLA
- memiliki dependency yang terdokumentasi
- mengikuti kebijakan platform
- mendukung evaluasi berkala

Tidak diperbolehkan terdapat layanan bersama yang berjalan di luar governance platform.

---

# Platform Security Responsibilities

Platform Services bertanggung jawab menjaga keamanan kapabilitas bersama.

Tanggung jawab tersebut meliputi:

- perlindungan identitas
- perlindungan konfigurasi
- perlindungan audit
- perlindungan dokumen
- perlindungan metadata
- perlindungan komunikasi internal
- perlindungan AI gateway
- perlindungan layanan integrasi

Setiap layanan harus menerapkan prinsip keamanan sesuai Security Architecture NovaNusa.

---

# Platform Service Level Agreement (SLA)

Seluruh Platform Services harus memiliki target kualitas layanan.

SLA digunakan untuk mengukur:

- ketersediaan layanan
- waktu respons
- waktu pemulihan
- ketepatan eksekusi
- keberhasilan proses
- kualitas layanan

SLA menjadi dasar evaluasi operasional platform.

---

# Platform Resilience

Platform Services harus tetap mampu beroperasi ketika terjadi gangguan pada sebagian komponen.

Prinsip resilience meliputi:

- fault tolerance
- graceful degradation
- recovery readiness
- isolation
- continuity
- controlled failure

Gangguan pada satu layanan tidak boleh menyebabkan kegagalan menyeluruh terhadap platform.

---

# Platform Reliability

Reliability memastikan bahwa Platform Services memberikan perilaku yang konsisten dalam jangka panjang.

Reliability dicapai melalui:

- kontrak layanan yang stabil
- lifecycle yang jelas
- observability
- auditability
- governance
- evaluasi berkala

Reliability merupakan karakteristik arsitektur, bukan sekadar hasil implementasi.

---

# Platform Scalability

Platform Services dirancang agar mampu berkembang mengikuti pertumbuhan organisasi.

Scalability mencakup:

- jumlah pengguna
- jumlah organisasi
- jumlah workflow
- jumlah dokumen
- jumlah knowledge
- jumlah AI request
- jumlah integrasi

Penambahan kapasitas tidak boleh mengubah kontrak layanan.

---

# Platform Availability

Platform Services harus dirancang agar tersedia sesuai kebutuhan operasional organisasi.

Availability mempertimbangkan:

- kebutuhan bisnis
- prioritas layanan
- ketergantungan antar layanan
- strategi pemulihan
- pemeliharaan terencana

Target availability ditentukan melalui kebijakan operasional, bukan oleh implementasi teknis tertentu.

---

# Platform Service Versioning

Setiap Platform Service memiliki versi yang terdokumentasi.

Versioning bertujuan untuk:

- menjaga kompatibilitas
- mendukung evolusi layanan
- mempermudah migrasi
- mengurangi risiko perubahan

Perubahan besar harus menghasilkan versi layanan yang baru.

---

# Platform Lifecycle Management

Platform Services mengikuti lifecycle berikut.

Proposed

↓

Designed

↓

Approved

↓

Published

↓

Operational

↓

Observed

↓

Improved

↓

Deprecated

↓

Retired

Lifecycle memastikan setiap layanan berkembang secara terkendali.

---

# Platform Extension Principles

Penambahan Platform Service baru harus memenuhi prinsip berikut.

- memiliki kebutuhan lintas domain
- tidak menduplikasi layanan yang telah ada
- memiliki kontrak yang jelas
- memiliki ownership
- mengikuti governance
- memenuhi standar keamanan
- memenuhi standar observability
- memenuhi standar auditability

Platform Services hanya ditambahkan apabila memberikan manfaat bagi lebih dari satu domain.

---

# Future Platform Readiness

Platform Services dirancang agar siap mendukung perkembangan NovaNusa dalam jangka panjang.

Kesiapan tersebut meliputi:

- domain baru
- layanan AI baru
- workflow baru
- integrasi baru
- organisasi baru
- model bisnis baru
- ekspansi nasional
- ekspansi internasional

Arsitektur Platform Services harus tetap relevan meskipun terjadi perubahan teknologi.

---

# Platform Evolution

Platform berkembang melalui proses evolusi yang terkendali.

Setiap evolusi harus:

- mempertahankan kompatibilitas
- menjaga governance
- meminimalkan dampak terhadap domain
- mempertahankan auditability
- mempertahankan observability

Evolusi tidak boleh menghilangkan prinsip dasar Platform Services.

---

# Penutup

Platform Services Architecture merupakan fondasi layanan bersama bagi seluruh ekosistem NovaNusa.

Dokumen ini mendefinisikan bagaimana kapabilitas lintas domain disediakan secara konsisten sehingga setiap domain dapat berfokus pada logika bisnisnya tanpa membangun kembali fungsi-fungsi umum.

Seluruh implementasi Platform Services wajib mengacu pada prinsip, struktur, dan tata kelola yang ditetapkan dalam dokumen ini.

Perubahan implementasi diperbolehkan selama tidak bertentangan dengan arsitektur Platform Services yang telah ditetapkan.

Dokumen ini menjadi acuan permanen bagi seluruh pengembangan layanan bersama NovaNusa.

---

**Status Dokumen:** FINAL

