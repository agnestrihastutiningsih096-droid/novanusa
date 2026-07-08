# 03 — NOVANUSA DOMAIN MODEL

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan resmi mengenai domain model NovaNusa.

Domain model menjelaskan entitas utama, relasi antar entitas, batas domain, dan cara sistem memahami dunia bisnis yang menjadi fokus NovaNusa.

Seluruh desain database, API, pipeline data, dashboard, matching engine, dan AI workflow wajib mengacu pada dokumen ini.

---

# Tujuan Dokumen

Dokumen ini bertujuan untuk menetapkan model konseptual NovaNusa secara lengkap.

Dokumen ini menjelaskan:

- domain utama dalam sistem;
- entitas utama;
- atribut konseptual setiap entitas;
- hubungan antar entitas;
- batas tanggung jawab setiap domain;
- prinsip pemodelan data;
- konsep single source of truth;
- konsep knowledge graph;
- hubungan antara data pemerintah, institusi, produk, principal, dan opportunity.

Dokumen ini tidak membahas struktur tabel database secara teknis.

Dokumen ini menjelaskan model bisnis dan model pengetahuan yang menjadi fondasi implementasi teknis.

---

# Prinsip Domain Model

Domain model NovaNusa wajib mengikuti prinsip berikut.

---

## 1. Entitas Harus Mewakili Dunia Nyata

Setiap entitas dalam NovaNusa harus mewakili objek nyata atau konsep bisnis yang jelas.

Contoh entitas:

- institusi;
- paket pengadaan;
- produk;
- principal;
- kategori;
- opportunity;
- kontak;
- wilayah.

Entitas yang tidak memiliki makna bisnis jelas tidak boleh menjadi pusat model.

---

## 2. Relasi Lebih Penting daripada Record

NovaNusa bukan hanya menyimpan daftar data.

NovaNusa harus memahami hubungan antar data.

Contoh:

- institusi memiliki banyak paket;
- paket memiliki kategori kebutuhan;
- kategori dapat cocok dengan produk;
- produk dimiliki oleh principal;
- opportunity muncul dari hubungan antara kebutuhan dan solusi.

Relasi inilah yang membentuk intelligence.

---

## 3. Setiap Entitas Memiliki Identitas

Setiap entitas utama harus memiliki identitas unik.

Identitas diperlukan untuk:

- menghindari duplikasi;
- menjaga konsistensi;
- melakukan audit;
- melacak histori;
- membangun relasi antar data.

Identitas internal sistem harus dibedakan dari identitas eksternal sumber data.

---

## 4. Data Mentah dan Data Olahan Harus Dibedakan

NovaNusa harus membedakan:

- data mentah dari sumber asli;
- data hasil cleaning;
- data hasil normalisasi;
- data hasil enrichment;
- data hasil analisis;
- data hasil rekomendasi.

Perbedaan ini penting agar sistem dapat diaudit.

---

## 5. Knowledge Harus Dapat Berkembang

Domain model harus memungkinkan penambahan relasi baru tanpa merusak relasi lama.

Contoh:

Hari ini produk hanya terhubung ke kategori.

Di masa depan produk dapat terhubung ke sektor, wilayah, regulasi, atau histori penggunaan.

Model harus mendukung pertumbuhan knowledge.

---

# Gambaran Besar Domain

NovaNusa terdiri dari sembilan domain utama.

1. Government Data Domain
2. Institution Domain
3. Procurement Domain
4. Product Domain
5. Principal Domain
6. Category Domain
7. Opportunity Domain
8. Contact Intelligence Domain
9. User Workflow Domain

Kesembilan domain ini saling terhubung dan membentuk satu sistem intelligence.

---

# 1. Government Data Domain

Government Data Domain adalah domain yang mencakup seluruh sumber informasi publik yang berasal dari ekosistem pemerintah.

Domain ini menjadi sumber bahan mentah utama NovaNusa.

---

## Tujuan Government Data Domain

Tujuan domain ini adalah menyediakan data dasar untuk memahami kebutuhan institusi pemerintah.

Data ini tidak langsung dianggap sebagai knowledge.

Data harus diproses terlebih dahulu melalui cleaning, normalisasi, enrichment, dan analisis.

---

## Sumber Data

Sumber data dalam domain ini dapat meliputi:

- SiRUP;
- e-Katalog;
- LPSE;
- website institusi;
- dokumen publik;
- portal kementerian;
- portal pemerintah daerah;
- informasi program;
- metadata organisasi;
- informasi anggaran publik.

---

## Entitas Utama

Entitas utama dalam Government Data Domain adalah:

- GovernmentSource;
- RawRecord;
- SourceDocument;
- DataImportBatch;
- DataQualityIssue.

---

## GovernmentSource

GovernmentSource merepresentasikan sumber data asal.

Contoh:

- SiRUP;
- e-Katalog;
- LPSE;
- website instansi;
- dokumen PDF publik;
- halaman profil organisasi.

Atribut konseptual:

- nama sumber;
- jenis sumber;
- URL sumber;
- status sumber;
- frekuensi pembaruan;
- metode pengambilan;
- tingkat kepercayaan;
- catatan penggunaan.

---

## RawRecord

RawRecord merepresentasikan data mentah yang diambil dari sumber.

RawRecord harus dipertahankan agar hasil analisis dapat ditelusuri kembali.

Atribut konseptual:

- source;
- external identifier;
- raw content;
- raw metadata;
- waktu pengambilan;
- status parsing;
- checksum;
- catatan error.

---

## SourceDocument

SourceDocument merepresentasikan dokumen publik yang digunakan sebagai sumber informasi.

Contoh:

- PDF pengadaan;
- dokumen rencana kerja;
- dokumen anggaran;
- dokumen profil organisasi;
- dokumen katalog.

Atribut konseptual:

- judul dokumen;
- sumber;
- tipe dokumen;
- tahun;
- URL;
- isi teks hasil ekstraksi;
- status ekstraksi;
- metadata dokumen.

---

## DataImportBatch

DataImportBatch merepresentasikan satu proses pengambilan data.

Atribut konseptual:

- nama batch;
- sumber;
- waktu mulai;
- waktu selesai;
- jumlah record;
- jumlah berhasil;
- jumlah gagal;
- status batch;
- log ringkasan.

---

## DataQualityIssue

DataQualityIssue merepresentasikan masalah kualitas data.

Contoh masalah:

- data kosong;
- format tidak valid;
- duplikasi;
- institusi tidak dikenali;
- kategori tidak jelas;
- nilai anggaran tidak wajar;
- konflik antar sumber.

Atribut konseptual:

- entitas terkait;
- jenis masalah;
- tingkat keparahan;
- sumber masalah;
- status penyelesaian;
- catatan reviewer.

---

# 2. Institution Domain

Institution Domain adalah domain yang merepresentasikan institusi pemerintah sebagai subjek utama analisis kebutuhan.

Institusi merupakan pusat dari banyak relasi dalam NovaNusa.

---

## Tujuan Institution Domain

Tujuan domain ini adalah membangun profil institusi yang konsisten, bersih, dan kaya konteks.

Profil institusi digunakan untuk:

- memahami histori kebutuhan;
- mengelompokkan sektor;
- menganalisis pola belanja;
- menentukan prioritas peluang;
- menemukan kontak relevan;
- menghubungkan institusi dengan produk dan principal.

---

## Entitas Utama

Entitas utama dalam Institution Domain adalah:

- Institution;
- InstitutionAlias;
- InstitutionType;
- GovernmentLevel;
- Sector;
- Region;
- InstitutionProfile;
- InstitutionRelationship.

---

## Institution

Institution adalah representasi utama sebuah organisasi pemerintah.

Atribut konseptual:

- nama resmi;
- nama normalisasi;
- jenis institusi;
- level pemerintahan;
- sektor;
- wilayah;
- status aktif;
- sumber identitas;
- tingkat keyakinan identitas;
- catatan validasi.

Institution menjadi single source of truth untuk identitas organisasi.

---

## InstitutionAlias

InstitutionAlias menyimpan variasi nama institusi.

Contoh:

- Dinas Pendidikan Kab. Sleman;
- Dinas Pendidikan Kabupaten Sleman;
- DINAS PENDIDIKAN SLEMAN;
- Disdik Sleman.

Atribut konseptual:

- institution;
- alias;
- sumber alias;
- tingkat keyakinan;
- status validasi.

Alias digunakan untuk matching data dari berbagai sumber.

---

## InstitutionType

InstitutionType menjelaskan jenis institusi.

Contoh:

- dinas;
- badan;
- sekretariat;
- rumah sakit;
- sekolah;
- universitas;
- puskesmas;
- kementerian;
- lembaga.

Atribut konseptual:

- nama tipe;
- deskripsi;
- parent type;
- aturan klasifikasi;
- contoh institusi.

---

## GovernmentLevel

GovernmentLevel menjelaskan level pemerintahan.

Contoh:

- pusat;
- provinsi;
- kabupaten;
- kota;
- kecamatan;
- desa;
- unit layanan.

Atribut konseptual:

- nama level;
- urutan hierarki;
- deskripsi;
- aturan klasifikasi.

---

## Sector

Sector menjelaskan sektor aktivitas institusi.

Contoh:

- pendidikan;
- kesehatan;
- infrastruktur;
- administrasi pemerintahan;
- komunikasi dan informatika;
- keuangan daerah;
- keamanan;
- sosial.

Atribut konseptual:

- nama sektor;
- deskripsi;
- keyword sektor;
- kategori kebutuhan umum.

---

## Region

Region merepresentasikan wilayah geografis.

Atribut konseptual:

- nama wilayah;
- tipe wilayah;
- provinsi;
- kabupaten/kota;
- kode wilayah jika tersedia;
- parent region;
- status validasi.

Region digunakan untuk analisis distribusi peluang.

---

## InstitutionProfile

InstitutionProfile adalah profil analitik institusi.

Profil ini merupakan hasil enrichment dan analisis.

Atribut konseptual:

- institution;
- ringkasan kebutuhan;
- kategori dominan;
- histori pengadaan;
- total estimasi anggaran;
- tren kebutuhan;
- pola belanja;
- tingkat potensi;
- catatan analis.

---

## InstitutionRelationship

InstitutionRelationship merepresentasikan hubungan antar institusi.

Contoh:

- dinas berada di bawah pemerintah daerah;
- puskesmas berada di bawah dinas kesehatan;
- sekolah berada di bawah dinas pendidikan;
- unit kerja berada di bawah kementerian.

Atribut konseptual:

- institution asal;
- institution tujuan;
- jenis relasi;
- sumber relasi;
- tingkat keyakinan;
- status aktif.

---

# 3. Procurement Domain

Procurement Domain adalah domain yang merepresentasikan kebutuhan, rencana, dan paket pengadaan.

Domain ini menjadi sumber utama opportunity detection.

---

## Tujuan Procurement Domain

Tujuan domain ini adalah memahami apa yang dibutuhkan institusi pemerintah.

Procurement Domain tidak hanya menyimpan nama paket.

Domain ini harus menangkap konteks kebutuhan.

---

## Entitas Utama

Entitas utama dalam Procurement Domain adalah:

- ProcurementPackage;
- ProcurementNeed;
- Budget;
- ProcurementMethod;
- FiscalYear;
- ProcurementStatus;
- ProcurementSourceReference.

---

## ProcurementPackage

ProcurementPackage merepresentasikan paket atau rencana pengadaan dari sumber resmi.

Atribut konseptual:

- nama paket;
- sumber;
- external identifier;
- institusi;
- satuan kerja;
- tahun anggaran;
- nilai pagu;
- metode pengadaan;
- status;
- lokasi;
- deskripsi;
- metadata sumber.

ProcurementPackage adalah data dasar, bukan langsung opportunity final.

---

## ProcurementNeed

ProcurementNeed merepresentasikan kebutuhan yang disimpulkan dari paket.

Satu paket dapat menghasilkan satu atau lebih kebutuhan.

Contoh:

Paket berjudul “Pengadaan Komputer dan Printer Kantor” dapat menghasilkan:

- kebutuhan komputer;
- kebutuhan printer;
- kebutuhan perangkat kerja kantor.

Atribut konseptual:

- procurement package;
- deskripsi kebutuhan;
- kategori kebutuhan;
- keyword terdeteksi;
- tingkat keyakinan;
- hasil klasifikasi;
- catatan reviewer.

---

## Budget

Budget merepresentasikan informasi anggaran terkait paket atau opportunity.

Atribut konseptual:

- nilai pagu;
- mata uang;
- tahun anggaran;
- sumber anggaran;
- status validasi;
- catatan nilai ekstrem;
- estimasi rentang jika diperlukan.

---

## ProcurementMethod

ProcurementMethod merepresentasikan metode pengadaan.

Contoh:

- e-purchasing;
- pengadaan langsung;
- tender;
- seleksi;
- penunjukan langsung;
- swakelola.

Atribut konseptual:

- nama metode;
- deskripsi;
- sumber;
- klasifikasi risiko;
- relevansi bisnis.

---

## FiscalYear

FiscalYear merepresentasikan tahun anggaran.

Atribut konseptual:

- tahun;
- periode aktif;
- status;
- catatan.

FiscalYear penting untuk analisis tren.

---

## ProcurementStatus

ProcurementStatus merepresentasikan status pengadaan.

Contoh:

- rencana;
- aktif;
- selesai;
- batal;
- tidak diketahui.

Atribut konseptual:

- nama status;
- deskripsi;
- sumber status;
- interpretasi sistem.

---

## ProcurementSourceReference

ProcurementSourceReference menyimpan rujukan ke sumber asli.

Atribut konseptual:

- procurement package;
- sumber;
- URL;
- external id;
- tanggal akses;
- metadata referensi.

Setiap analisis harus dapat kembali ke referensi sumber.

---

# 4. Product Domain

Product Domain merepresentasikan produk, solusi, atau barang yang dapat ditawarkan untuk menjawab kebutuhan institusi.

---

## Tujuan Product Domain

Tujuan domain ini adalah membuat sistem memahami produk secara semantik.

Produk tidak cukup hanya disimpan sebagai nama.

Produk harus memiliki kategori, fungsi, spesifikasi, relasi, dan konteks penggunaan.

---

## Entitas Utama

Entitas utama dalam Product Domain adalah:

- Product;
- ProductCategory;
- ProductBrand;
- ProductSpecification;
- ProductKeyword;
- ProductAlternative;
- ProductBundle;
- ProductSectorFit.

---

## Product

Product adalah entitas utama yang merepresentasikan barang atau solusi.

Atribut konseptual:

- nama produk;
- merek;
- principal;
- kategori;
- deskripsi;
- fungsi utama;
- spesifikasi ringkas;
- status aktif;
- sumber data produk;
- catatan validasi.

Product menjadi dasar pencocokan dengan kebutuhan.

---

## ProductCategory

ProductCategory menjelaskan kategori produk.

Contoh:

- laptop;
- desktop;
- printer;
- scanner;
- CCTV;
- networking;
- server;
- storage;
- audio;
- camera;
- drone;
- alat kesehatan;
- furniture kantor.

Atribut konseptual:

- nama kategori;
- parent category;
- deskripsi;
- keyword kategori;
- aturan klasifikasi;
- tingkat prioritas bisnis.

---

## ProductBrand

ProductBrand merepresentasikan merek produk.

Atribut konseptual:

- nama brand;
- principal;
- kategori utama;
- status aktif;
- catatan.

Brand dapat berbeda dari principal, tetapi harus dapat dihubungkan.

---

## ProductSpecification

ProductSpecification menyimpan spesifikasi penting produk.

Atribut konseptual:

- produk;
- nama spesifikasi;
- nilai spesifikasi;
- satuan;
- kategori spesifikasi;
- sumber spesifikasi.

Spesifikasi digunakan untuk matching lanjutan.

---

## ProductKeyword

ProductKeyword menyimpan kata kunci yang relevan dengan produk.

Contoh:

- komputer;
- PC;
- workstation;
- laptop;
- printer;
- jaringan;
- kamera pengawas.

Atribut konseptual:

- produk;
- keyword;
- jenis keyword;
- bobot;
- sumber;
- status validasi.

---

## ProductAlternative

ProductAlternative menyimpan relasi produk pengganti.

Atribut konseptual:

- produk utama;
- produk alternatif;
- alasan alternatif;
- tingkat kesesuaian;
- catatan.

---

## ProductBundle

ProductBundle merepresentasikan kumpulan produk yang sering ditawarkan bersama.

Contoh:

- komputer + printer;
- CCTV + NVR + storage;
- laptop + docking + monitor;
- networking + rack + UPS.

Atribut konseptual:

- nama bundle;
- produk anggota;
- kebutuhan yang dilayani;
- sektor relevan;
- catatan.

---

## ProductSectorFit

ProductSectorFit menjelaskan kecocokan produk terhadap sektor tertentu.

Contoh:

- laptop cocok untuk pendidikan;
- alat kesehatan cocok untuk rumah sakit;
- CCTV cocok untuk keamanan;
- networking cocok untuk Diskominfo.

Atribut konseptual:

- produk;
- sektor;
- tingkat kecocokan;
- alasan;
- sumber validasi.

---

# 5. Principal Domain

Principal Domain merepresentasikan pemilik merek, produsen, distributor utama, atau perusahaan penyedia solusi yang berhubungan dengan produk.

---

## Tujuan Principal Domain

Tujuan domain ini adalah memahami siapa penyedia solusi dan bagaimana portofolio mereka berhubungan dengan kebutuhan pemerintah.

Principal Domain penting untuk strategi bisnis, kemitraan, dan prioritas penawaran.

---

## Entitas Utama

Entitas utama dalam Principal Domain adalah:

- Principal;
- PrincipalProfile;
- PrincipalProductPortfolio;
- PrincipalSectorFocus;
- PrincipalRegionFocus;
- PrincipalRelationship.

---

## Principal

Principal adalah entitas utama perusahaan penyedia solusi atau pemilik portofolio produk.

Atribut konseptual:

- nama principal;
- nama legal;
- jenis principal;
- kategori utama;
- website;
- status kerja sama;
- catatan.

---

## PrincipalProfile

PrincipalProfile menyimpan informasi analitik principal.

Atribut konseptual:

- principal;
- ringkasan profil;
- keunggulan utama;
- sektor target;
- kategori produk;
- potensi pasar pemerintah;
- catatan strategi.

---

## PrincipalProductPortfolio

PrincipalProductPortfolio menghubungkan principal dengan produk.

Atribut konseptual:

- principal;
- produk;
- brand;
- kategori;
- status aktif;
- sumber portofolio.

---

## PrincipalSectorFocus

PrincipalSectorFocus menjelaskan sektor yang relevan untuk principal.

Atribut konseptual:

- principal;
- sektor;
- tingkat relevansi;
- alasan;
- catatan.

---

## PrincipalRegionFocus

PrincipalRegionFocus menjelaskan wilayah prioritas atau cakupan principal.

Atribut konseptual:

- principal;
- wilayah;
- tingkat prioritas;
- alasan;
- catatan.

---

## PrincipalRelationship

PrincipalRelationship merepresentasikan hubungan antar principal, distributor, reseller, atau partner.

Atribut konseptual:

- principal asal;
- principal tujuan;
- jenis relasi;
- status;
- sumber;
- catatan.

---

# 6. Category Domain

Category Domain merepresentasikan sistem klasifikasi kebutuhan, produk, institusi, dan opportunity.

Kategori merupakan jembatan penting antara data pemerintah dan data produk.

---

## Tujuan Category Domain

Tujuan domain ini adalah menyediakan bahasa klasifikasi yang konsisten.

Tanpa kategori yang konsisten, sistem tidak dapat melakukan matching dan analisis secara akurat.

---

## Entitas Utama

Entitas utama dalam Category Domain adalah:

- Category;
- CategoryAlias;
- CategoryRule;
- CategoryHierarchy;
- CategoryMapping;
- CategoryConfidence.

---

## Category

Category adalah klasifikasi utama yang digunakan dalam sistem.

Atribut konseptual:

- nama kategori;
- tipe kategori;
- deskripsi;
- parent category;
- status aktif;
- prioritas bisnis.

Kategori dapat digunakan untuk:

- paket;
- kebutuhan;
- produk;
- principal;
- opportunity.

---

## CategoryAlias

CategoryAlias menyimpan variasi istilah untuk kategori.

Contoh:

- komputer;
- PC;
- desktop;
- perangkat TIK;
- workstation.

Atribut konseptual:

- category;
- alias;
- bahasa;
- sumber;
- bobot;
- status validasi.

---

## CategoryRule

CategoryRule menyimpan aturan klasifikasi.

Atribut konseptual:

- category;
- keyword positif;
- keyword negatif;
- kondisi tambahan;
- bobot;
- catatan.

Aturan ini dapat digunakan oleh matching engine dan AI classifier.

---

## CategoryHierarchy

CategoryHierarchy menjelaskan hubungan parent-child antar kategori.

Contoh:

- IT Hardware
  - Laptop
  - Desktop
  - Printer
  - Server
  - Networking

Atribut konseptual:

- parent category;
- child category;
- urutan;
- catatan.

---

## CategoryMapping

CategoryMapping menghubungkan kategori dari sumber eksternal dengan kategori internal NovaNusa.

Atribut konseptual:

- sumber eksternal;
- kategori eksternal;
- kategori internal;
- tingkat keyakinan;
- status validasi.

---

## CategoryConfidence

CategoryConfidence menyimpan tingkat keyakinan klasifikasi.

Atribut konseptual:

- entitas terkait;
- kategori;
- confidence score;
- metode klasifikasi;
- alasan;
- status reviewer.

---

# 7. Opportunity Domain

Opportunity Domain adalah domain yang merepresentasikan peluang bisnis hasil analisis NovaNusa.

Opportunity bukan data mentah.

Opportunity adalah hasil pemahaman sistem terhadap kebutuhan, produk, institusi, dan konteks bisnis.

---

## Tujuan Opportunity Domain

Tujuan domain ini adalah menyediakan daftar peluang yang dapat ditindaklanjuti.

Opportunity harus memiliki:

- sumber yang jelas;
- kebutuhan yang jelas;
- institusi yang jelas;
- kategori yang jelas;
- alasan rekomendasi;
- prioritas;
- status tindak lanjut.

---

## Entitas Utama

Entitas utama dalam Opportunity Domain adalah:

- Opportunity;
- OpportunitySource;
- OpportunityNeed;
- OpportunityProductMatch;
- OpportunityPrincipalMatch;
- OpportunityScore;
- OpportunityStatus;
- OpportunityAction.

---

## Opportunity

Opportunity adalah entitas utama peluang bisnis.

Atribut konseptual:

- judul opportunity;
- institusi;
- sumber opportunity;
- kebutuhan utama;
- kategori;
- estimasi nilai;
- tahun;
- status;
- prioritas;
- ringkasan rekomendasi;
- catatan analis.

---

## OpportunitySource

OpportunitySource menjelaskan asal peluang.

Satu opportunity dapat berasal dari:

- satu paket pengadaan;
- beberapa paket terkait;
- pola historis;
- dokumen publik;
- hasil analisis AI;
- input manual pengguna.

Atribut konseptual:

- opportunity;
- jenis sumber;
- referensi sumber;
- tingkat keyakinan;
- catatan.

---

## OpportunityNeed

OpportunityNeed menjelaskan kebutuhan dalam opportunity.

Atribut konseptual:

- opportunity;
- deskripsi kebutuhan;
- kategori;
- keyword;
- confidence score;
- catatan.

---

## OpportunityProductMatch

OpportunityProductMatch menghubungkan opportunity dengan produk yang relevan.

Atribut konseptual:

- opportunity;
- produk;
- tingkat kecocokan;
- alasan kecocokan;
- sumber matching;
- status review.

---

## OpportunityPrincipalMatch

OpportunityPrincipalMatch menghubungkan opportunity dengan principal yang relevan.

Atribut konseptual:

- opportunity;
- principal;
- tingkat relevansi;
- produk terkait;
- alasan;
- status review.

---

## OpportunityScore

OpportunityScore menyimpan skor prioritas peluang.

Skor dapat mempertimbangkan:

- nilai anggaran;
- kecocokan produk;
- kualitas kontak;
- relevansi principal;
- urgensi;
- sektor;
- histori;
- confidence.

Atribut konseptual:

- opportunity;
- total score;
- score component;
- metode scoring;
- alasan skor;
- waktu perhitungan.

---

## OpportunityStatus

OpportunityStatus merepresentasikan status peluang.

Contoh:

- new;
- review;
- ready;
- approved;
- contacted;
- follow up;
- won;
- lost;
- hold;
- archived.

Atribut konseptual:

- nama status;
- deskripsi;
- urutan workflow;
- aturan transisi.

---

## OpportunityAction

OpportunityAction merepresentasikan tindakan terhadap opportunity.

Contoh:

- review;
- approve;
- contact;
- send email;
- call;
- follow up;
- archive;
- assign to user.

Atribut konseptual:

- opportunity;
- action type;
- actor;
- waktu;
- hasil;
- catatan.

---

# 8. Contact Intelligence Domain

Contact Intelligence Domain merepresentasikan data kontak publik dan jalur komunikasi institusi.

Domain ini harus dikelola secara hati-hati, etis, dan berbasis sumber yang sah.

---

## Tujuan Contact Intelligence Domain

Tujuan domain ini adalah membantu pengguna menemukan jalur komunikasi yang relevan dan dapat diverifikasi.

Contact intelligence bukan alat spam.

Contact intelligence adalah alat validasi dan prioritisasi komunikasi bisnis.

---

## Entitas Utama

Entitas utama dalam Contact Intelligence Domain adalah:

- ContactPoint;
- ContactSource;
- ContactValidation;
- ContactRole;
- CommunicationChannel;
- OutreachHistory.

---

## ContactPoint

ContactPoint merepresentasikan informasi kontak.

Atribut konseptual:

- institusi;
- tipe kontak;
- nilai kontak;
- label;
- unit kerja;
- status aktif;
- sumber;
- tingkat keyakinan;
- catatan.

Contoh tipe kontak:

- email;
- telepon;
- website;
- alamat;
- formulir kontak.

---

## ContactSource

ContactSource menjelaskan asal data kontak.

Atribut konseptual:

- contact point;
- URL sumber;
- jenis sumber;
- tanggal akses;
- metode pengambilan;
- catatan.

---

## ContactValidation

ContactValidation menyimpan status validasi kontak.

Atribut konseptual:

- contact point;
- status validasi;
- metode validasi;
- waktu validasi;
- hasil validasi;
- catatan reviewer.

---

## ContactRole

ContactRole menjelaskan peran umum kontak.

Contoh:

- sekretariat;
- pengadaan;
- layanan informasi;
- humas;
- umum;
- tidak diketahui.

Atribut konseptual:

- nama role;
- deskripsi;
- aturan klasifikasi;
- tingkat relevansi.

---

## CommunicationChannel

CommunicationChannel menjelaskan jalur komunikasi yang digunakan.

Contoh:

- email;
- telepon;
- website;
- surat resmi;
- form kontak.

Atribut konseptual:

- nama channel;
- deskripsi;
- aturan penggunaan;
- risiko;
- catatan etika.

---

## OutreachHistory

OutreachHistory menyimpan histori komunikasi yang dilakukan melalui sistem atau dicatat oleh pengguna.

Atribut konseptual:

- opportunity;
- institusi;
- contact point;
- channel;
- waktu komunikasi;
- isi ringkas;
- status;
- hasil;
- user;
- catatan.

---

# 9. User Workflow Domain

User Workflow Domain merepresentasikan aktivitas pengguna dalam sistem.

Domain ini penting untuk audit, kontrol, dan kolaborasi.

---

## Tujuan User Workflow Domain

Tujuan domain ini adalah memastikan setiap tindakan penting dapat dilacak.

NovaNusa harus mendukung kolaborasi manusia di atas data dan AI.

---

## Entitas Utama

Entitas utama dalam User Workflow Domain adalah:

- User;
- Role;
- Permission;
- ReviewTask;
- Approval;
- Assignment;
- AuditLog;
- UserNote.

---

## User

User merepresentasikan pengguna sistem.

Atribut konseptual:

- nama;
- email;
- status;
- role;
- organisasi;
- waktu dibuat;
- waktu terakhir aktif.

---

## Role

Role merepresentasikan peran pengguna.

Contoh:

- administrator;
- analis;
- sales;
- manajemen;
- principal viewer.

Atribut konseptual:

- nama role;
- deskripsi;
- scope akses;
- batas kewenangan.

---

## Permission

Permission merepresentasikan hak akses granular.

Contoh:

- melihat data;
- mengubah data;
- melakukan review;
- approve komunikasi;
- mengelola user;
- mengakses dashboard principal.

Atribut konseptual:

- nama permission;
- deskripsi;
- role terkait;
- batas domain.

---

## ReviewTask

ReviewTask merepresentasikan tugas validasi manusia.

Atribut konseptual:

- jenis review;
- entitas terkait;
- assigned user;
- status;
- prioritas;
- deadline;
- hasil review;
- catatan.

---

## Approval

Approval merepresentasikan persetujuan sebelum tindakan penting.

Contoh:

- approval kontak;
- approval opportunity;
- approval email;
- approval rekomendasi;
- approval perubahan data.

Atribut konseptual:

- entitas terkait;
- jenis approval;
- approver;
- status approval;
- waktu;
- catatan.

---

## Assignment

Assignment merepresentasikan pembagian tanggung jawab.

Atribut konseptual:

- entitas terkait;
- assigned user;
- assigned role;
- status;
- waktu assignment;
- catatan.

---

## AuditLog

AuditLog merepresentasikan jejak perubahan dan tindakan.

Atribut konseptual:

- actor;
- action;
- entitas;
- waktu;
- nilai sebelum;
- nilai sesudah;
- sumber perubahan;
- catatan.

AuditLog wajib ada untuk tindakan penting.

---

## UserNote

UserNote menyimpan catatan pengguna terhadap entitas.

Atribut konseptual:

- user;
- entitas terkait;
- isi catatan;
- visibility;
- waktu dibuat;
- waktu diubah.

---

# Relasi Utama Antar Domain

Relasi antar domain adalah inti dari NovaNusa.

Berikut adalah relasi utama yang wajib dipertahankan.

---

## Institusi dan Pengadaan

Satu Institution dapat memiliki banyak ProcurementPackage.

Satu ProcurementPackage harus terkait dengan satu Institution utama.

Relasi ini digunakan untuk memahami histori kebutuhan institusi.

---

## Pengadaan dan Kebutuhan

Satu ProcurementPackage dapat menghasilkan satu atau lebih ProcurementNeed.

ProcurementNeed adalah hasil pemahaman terhadap isi paket.

Relasi ini digunakan untuk klasifikasi kebutuhan.

---

## Kebutuhan dan Kategori

Satu ProcurementNeed dapat memiliki satu atau lebih Category.

Kategori dapat memiliki confidence score.

Relasi ini digunakan untuk product matching.

---

## Kategori dan Produk

Satu Category dapat terkait dengan banyak Product.

Satu Product dapat terkait dengan banyak Category.

Relasi ini memungkinkan pencocokan kebutuhan dengan solusi.

---

## Produk dan Principal

Satu Product dapat terkait dengan satu atau lebih Principal.

Satu Principal dapat memiliki banyak Product.

Relasi ini digunakan untuk strategi principal.

---

## Institusi dan Opportunity

Satu Institution dapat memiliki banyak Opportunity.

Opportunity menjadi jembatan antara kebutuhan institusi dan tindakan bisnis.

---

## Opportunity dan Produk

Satu Opportunity dapat memiliki banyak ProductMatch.

Setiap ProductMatch harus memiliki alasan kecocokan.

---

## Opportunity dan Principal

Satu Opportunity dapat memiliki banyak PrincipalMatch.

Setiap PrincipalMatch harus memiliki alasan relevansi.

---

## Institusi dan Kontak

Satu Institution dapat memiliki banyak ContactPoint.

ContactPoint harus memiliki sumber dan status validasi.

---

## Opportunity dan Workflow

Satu Opportunity dapat memiliki banyak ReviewTask, Approval, Assignment, dan OutreachHistory.

Relasi ini memastikan opportunity dapat dikelola secara operasional.

---

# Konsep Single Source of Truth

Single source of truth berarti setiap entitas utama hanya memiliki satu representasi resmi dalam sistem.

Entitas yang wajib memiliki single source of truth:

- Institution;
- Product;
- Principal;
- Category;
- Region;
- Opportunity;
- ContactPoint.

Data dari sumber eksternal tidak langsung menjadi master.

Data eksternal harus melalui proses:

1. ingestion;
2. cleaning;
3. normalization;
4. matching;
5. validation;
6. promotion to master.

---

# Konsep Raw Data vs Master Data

NovaNusa harus membedakan raw data dan master data.

Raw data adalah data asli dari sumber eksternal.

Master data adalah data yang telah diproses dan digunakan sebagai acuan sistem.

Raw data tidak boleh dihapus hanya karena sudah ada master data.

Raw data diperlukan untuk audit dan penelusuran asal informasi.

---

# Konsep Confidence

Tidak semua data memiliki tingkat kepastian yang sama.

NovaNusa harus menggunakan konsep confidence untuk menunjukkan tingkat keyakinan.

Confidence dapat diterapkan pada:

- identitas institusi;
- klasifikasi kategori;
- hasil matching produk;
- validasi kontak;
- relevansi principal;
- skor opportunity;
- hasil AI.

Confidence membantu manusia memutuskan apakah hasil sistem dapat langsung digunakan atau perlu direview.

---

# Konsep Human Review

Human review adalah bagian resmi dari domain model.

Data atau rekomendasi yang memiliki risiko tinggi harus dapat masuk ke workflow review.

Contoh yang perlu review:

- institusi ambigu;
- kontak tidak yakin;
- kategori tidak jelas;
- hasil matching lemah;
- opportunity bernilai besar;
- komunikasi keluar;
- klaim produk;
- hasil AI yang tidak memiliki dasar cukup.

---

# Konsep Knowledge Graph

NovaNusa harus dipahami sebagai knowledge graph, bukan sekadar relational record.

Knowledge graph berarti sistem memahami node dan relasi.

Contoh node:

- Institution;
- Product;
- Principal;
- Category;
- ProcurementPackage;
- Opportunity;
- ContactPoint;
- Region.

Contoh relasi:

- Institution HAS_PACKAGE ProcurementPackage;
- ProcurementPackage EXPRESSES_NEED ProcurementNeed;
- ProcurementNeed CLASSIFIED_AS Category;
- Product BELONGS_TO Category;
- Product PROVIDED_BY Principal;
- Opportunity TARGETS Institution;
- Opportunity MATCHES Product;
- Opportunity RELEVANT_TO Principal;
- Institution HAS_CONTACT ContactPoint.

Knowledge graph memungkinkan NovaNusa menghasilkan insight yang lebih kaya.

---

# Aturan Penamaan Entitas

Penamaan entitas dalam implementasi harus mengikuti prinsip berikut:

- menggunakan istilah bisnis yang jelas;
- konsisten antara dokumen, database, API, dan UI;
- tidak menggunakan singkatan yang membingungkan;
- membedakan data mentah dan data master;
- membedakan source reference dan entity utama;
- menggunakan bahasa Inggris untuk nama teknis jika diperlukan;
- menggunakan bahasa Indonesia yang jelas untuk tampilan pengguna.

Contoh:

- Institution untuk entitas institusi;
- ProcurementPackage untuk paket pengadaan;
- Opportunity untuk peluang;
- ProductMatch untuk hasil pencocokan produk;
- ContactPoint untuk titik kontak.

---

# Aturan Relasi

Setiap relasi penting harus memiliki alasan bisnis.

Relasi tidak boleh dibuat hanya karena mudah secara teknis.

Relasi harus dapat menjawab pertanyaan seperti:

- mengapa entitas ini berhubungan?
- dari mana hubungan ini berasal?
- apakah hubungan ini pasti atau hasil inferensi?
- siapa atau apa yang membuat hubungan ini?
- kapan hubungan ini dibuat?
- apakah hubungan ini masih aktif?

Relasi yang berasal dari AI harus diberi penanda sebagai hasil inferensi.

---

# Aturan Audit Domain

Setiap perubahan pada entitas penting harus dapat diaudit.

Audit minimal harus mencakup:

- siapa yang mengubah;
- apa yang diubah;
- kapan diubah;
- nilai sebelum;
- nilai sesudah;
- alasan perubahan jika tersedia;
- sumber perubahan.

Audit penting untuk menjaga kepercayaan platform.

---

# Risiko Domain Model

Beberapa risiko utama dalam domain model NovaNusa adalah:

- duplikasi institusi;
- kategori terlalu luas;
- kategori terlalu sempit;
- produk tidak lengkap;
- principal tidak terhubung dengan produk;
- kontak tidak valid;
- opportunity terlalu banyak tetapi tidak berkualitas;
- hasil AI dianggap sebagai kebenaran final;
- relasi tidak dapat dijelaskan;
- raw data tercampur dengan master data.

Risiko tersebut harus dikelola melalui desain domain yang disiplin.

---

# Kriteria Keberhasilan Domain Model

Domain model dianggap berhasil apabila:

- setiap entitas utama memiliki makna bisnis yang jelas;
- relasi antar entitas dapat dijelaskan;
- sistem mampu membedakan raw data dan master data;
- sistem mampu membangun single source of truth;
- opportunity dapat ditelusuri ke sumber data;
- product matching memiliki alasan;
- principal matching memiliki alasan;
- kontak memiliki sumber;
- AI output memiliki confidence;
- human review dapat dilakukan pada data berisiko;
- model dapat berkembang tanpa merusak fondasi.

---

# Penutup

Dokumen ini menetapkan domain model resmi NovaNusa.

Domain model ini menjadi dasar untuk seluruh desain teknis berikutnya, termasuk database, API, dashboard, pipeline data, matching engine, AI workflow, dan audit system.

Seluruh pengembangan NovaNusa wajib menjaga konsistensi dengan domain model ini.

Apabila di masa depan terdapat penambahan entitas atau relasi baru, penambahan tersebut harus memperkuat model pengetahuan NovaNusa dan tidak boleh merusak prinsip single source of truth, explainability, auditability, dan human-centered decision.

Dengan domain model yang jelas, NovaNusa dapat berkembang sebagai platform intelligence yang kokoh, konsisten, dan siap diperluas secara bertahap.

---

**Status Dokumen:** FINAL
