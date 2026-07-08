# 06 — NOVANUSA APPLICATION ARCHITECTURE

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan resmi arsitektur aplikasi NovaNusa.

Dokumen ini menerjemahkan System Architecture menjadi rancangan aplikasi yang siap menjadi dasar implementasi modul, service, dashboard, workflow, dan integrasi internal NovaNusa.

Dokumen ini mengacu pada:

- `docs/00_PROJECT_CHARTER.md`
- `docs/01_SYSTEM_VISION.md`
- `docs/02_SYSTEM_SCOPE.md`
- `docs/03_DOMAIN_MODEL.md`
- `docs/04_DATA_ARCHITECTURE.md`
- `docs/05_SYSTEM_ARCHITECTURE.md`

---

# 1. Tujuan Dokumen

Dokumen ini bertujuan menjelaskan struktur aplikasi NovaNusa secara resmi.

Application Architecture menjawab pertanyaan:

- Aplikasi NovaNusa dibagi menjadi modul apa saja?
- Setiap modul bertanggung jawab atas apa?
- Bagaimana modul saling berinteraksi?
- Bagaimana pengguna berinteraksi dengan sistem?
- Bagaimana data, AI, workflow, dan audit masuk ke aplikasi?
- Bagaimana aplikasi dikembangkan secara bertahap tanpa merusak fondasi?

Dokumen ini tidak membahas kode, framework, atau detail teknis implementasi tertentu.

---

# 2. Prinsip Arsitektur Aplikasi

Aplikasi NovaNusa wajib mengikuti prinsip berikut:

1. Modular.
2. Data-first.
3. Human-in-the-loop.
4. Explainable.
5. Auditable.
6. Configurable.
7. Scalable.
8. Maintainable.
9. Safe for external action.
10. Consistent with domain model.

Aplikasi tidak boleh dibangun hanya sebagai dashboard tabel.

NovaNusa adalah decision support application berbasis intelligence.

---

# 3. Struktur Besar Aplikasi

Aplikasi NovaNusa terdiri dari lapisan berikut:

1. Presentation Layer
2. Application Service Layer
3. Workflow Layer
4. Intelligence Layer
5. AI Assistance Layer
6. Data Access Layer
7. Audit and Governance Layer
8. Configuration Layer

Setiap lapisan memiliki tanggung jawab yang berbeda.

---

# 4. Presentation Layer

Presentation Layer adalah antarmuka yang digunakan pengguna untuk memahami data, meninjau rekomendasi, dan mengambil keputusan.

Presentation Layer mencakup:

- Dashboard utama.
- Halaman institution intelligence.
- Halaman need intelligence.
- Halaman product intelligence.
- Halaman opportunity pipeline.
- Halaman recommendation review.
- Halaman workflow.
- Halaman audit.
- Halaman configuration.
- Halaman reporting.

Presentation Layer tidak boleh langsung mengambil keputusan bisnis.

Presentation Layer menampilkan data, evidence, status, risiko, dan tindakan yang tersedia.

---

# 5. Application Service Layer

Application Service Layer mengatur logika aplikasi.

Lapisan ini bertanggung jawab untuk:

- Mengambil data siap pakai dari Data Access Layer.
- Menyusun data untuk dashboard.
- Mengatur proses review.
- Mengatur proses approval.
- Mengatur pemanggilan intelligence module.
- Mengatur pemanggilan AI assistance.
- Menjamin validasi tindakan pengguna.
- Mengirim event ke audit log.
- Menjaga batas antar modul.

Application Service Layer adalah pusat koordinasi aplikasi.

---

# 6. Workflow Layer

Workflow Layer mengatur siklus hidup opportunity, recommendation, review, approval, hold, rejection, follow-up, dan archive.

Workflow Layer wajib memastikan:

- Setiap status jelas.
- Setiap perubahan status memiliki aturan.
- Setiap tindakan memiliki aktor.
- Setiap tindakan memiliki timestamp.
- Setiap tindakan tercatat dalam audit.
- Tindakan eksternal tidak terjadi tanpa approval.

Workflow Layer adalah penjaga keamanan proses NovaNusa.

---

# 7. Intelligence Layer

Intelligence Layer berisi kemampuan analisis utama NovaNusa.

Lapisan ini mencakup:

- Need Detection.
- Product Matching.
- Principal Matching.
- Opportunity Scoring.
- Recommendation Generation.
- Risk Detection.
- Data Quality Assessment.
- Gap Analysis.

Intelligence Layer tidak boleh menghasilkan output tanpa evidence.

Setiap hasil intelligence harus memiliki:

- Source reference.
- Evidence.
- Confidence.
- Risk flag.
- Explanation.
- Version.

---

# 8. AI Assistance Layer

AI Assistance Layer membantu pengguna memahami dan mengolah informasi.

AI dapat digunakan untuk:

- Ringkasan institusi.
- Ringkasan kebutuhan.
- Penjelasan opportunity.
- Draft komunikasi.
- Saran tindak lanjut.
- Pemeriksaan inkonsistensi.
- Klasifikasi berbantuan.
- Penyusunan insight.

AI Assistance Layer tidak boleh menjadi otoritas final.

Output AI harus dapat direview dan tidak boleh mengubah data inti tanpa persetujuan manusia.

---

# 9. Data Access Layer

Data Access Layer mengatur akses aplikasi ke data NovaNusa.

Lapisan ini bertanggung jawab untuk:

- Mengambil raw data bila dibutuhkan audit.
- Mengambil normalized data.
- Mengambil derived data.
- Mengambil knowledge entity.
- Mengambil recommendation.
- Mengambil workflow status.
- Mengambil audit log.
- Menyediakan query terstruktur untuk aplikasi.

Data Access Layer harus menjaga konsistensi antara aplikasi dan Data Architecture.

---

# 10. Audit and Governance Layer

Audit and Governance Layer mencatat aktivitas penting dalam aplikasi.

Aktivitas yang wajib dicatat:

- User login bila tersedia.
- Data view penting bila diperlukan.
- Review.
- Approval.
- Rejection.
- Hold.
- Status change.
- Configuration change.
- AI generation.
- Export.
- External communication preparation.
- Manual correction.
- Reprocessing trigger.

Audit tidak boleh opsional.

---

# 11. Configuration Layer

Configuration Layer menyimpan aturan aplikasi yang dapat diubah secara terkendali.

Konfigurasi mencakup:

- Threshold scoring.
- Threshold risk.
- Kategori kebutuhan.
- Mapping rule.
- Prompt policy.
- Approval rule.
- Workflow status.
- Role permission.
- Report setting.
- Export policy.

Perubahan konfigurasi harus tercatat dalam audit log.

---

# 12. Modul Aplikasi Utama

NovaNusa memiliki modul aplikasi utama berikut:

1. Home Dashboard
2. Institution Module
3. Need Module
4. Product Module
5. Principal Module
6. Opportunity Module
7. Recommendation Module
8. Workflow Module
9. AI Assistant Module
10. Reporting Module
11. Audit Module
12. Configuration Module

---

# 13. Home Dashboard

Home Dashboard adalah pintu masuk utama pengguna.

Home Dashboard menampilkan:

- Total opportunities.
- Opportunities by status.
- Top institutions.
- Top need categories.
- Top product categories.
- High priority opportunities.
- Review required items.
- Risk summary.
- Recent user actions.
- Data quality summary.
- Latest processing status.

Home Dashboard harus bersifat ringkas tetapi dapat di-drill-down.

---

# 14. Institution Module

Institution Module mengelola intelligence per institusi.

Modul ini menampilkan:

- Nama institusi.
- Wilayah.
- Jenis institusi.
- Kebutuhan yang terdeteksi.
- Paket terkait.
- Opportunity terkait.
- Contact intelligence.
- Recommendation terkait.
- Riwayat workflow.
- Catatan pengguna.
- Risk flag.
- Audit trail.

Institution Module harus membantu pengguna memahami konteks institusi sebelum mengambil tindakan.

---

# 15. Need Module

Need Module mengelola kebutuhan yang terdeteksi.

Modul ini menampilkan:

- Need name.
- Need category.
- Source package.
- Evidence text.
- Institution.
- Region.
- Confidence.
- Risk flag.
- Product match.
- Opportunity relation.
- Review status.

Need Module adalah pusat pemahaman permintaan pasar institusi.

---

# 16. Product Module

Product Module mengelola produk dan solusi.

Modul ini menampilkan:

- Nama produk.
- Kategori produk.
- Principal.
- Spesifikasi utama.
- Need category yang cocok.
- Opportunity yang relevan.
- Mapping confidence.
- Availability status.
- Risk notes.
- Source.
- Version.

Product Module harus mendukung product intelligence dan product matching.

---

# 17. Principal Module

Principal Module mengelola principal atau pemilik produk.

Modul ini menampilkan:

- Nama principal.
- Kategori produk.
- Produk terkait.
- Need category yang relevan.
- Opportunity potensial.
- Gap opportunity.
- Contact atau notes bila tersedia.
- Status hubungan.
- Catatan strategis.

Principal Module mendukung pengembangan NovaNusa sebagai platform pencocokan kebutuhan dan supply.

---

# 18. Opportunity Module

Opportunity Module adalah modul inti aplikasi.

Modul ini menampilkan:

- Opportunity ID.
- Institution.
- Need.
- Product match.
- Principal match.
- Budget context bila tersedia.
- Score.
- Score explanation.
- Confidence.
- Risk level.
- Recommendation.
- Workflow status.
- Evidence.
- User notes.
- Audit trail.

Opportunity Module harus memungkinkan pengguna melakukan review mendalam sebelum approval.

---

# 19. Recommendation Module

Recommendation Module mengelola rekomendasi sistem.

Modul ini menampilkan:

- Recommendation title.
- Related opportunity.
- Related institution.
- Related need.
- Related product.
- Reasoning.
- Evidence.
- Confidence.
- Risk flag.
- Suggested action.
- Review status.
- Approval status.

Recommendation Module tidak boleh menampilkan rekomendasi tanpa alasan.

---

# 20. Workflow Module

Workflow Module mengelola antrian kerja.

Tampilan workflow minimal mencakup:

- New.
- Processed.
- Matched.
- Scored.
- Recommended.
- Review Required.
- Approved.
- Hold.
- Rejected.
- Follow Up.
- Completed.
- Archived.

Workflow Module harus menampilkan item berdasarkan prioritas, risiko, dan status.

---

# 21. AI Assistant Module

AI Assistant Module menyediakan bantuan berbasis AI dalam konteks aplikasi.

Fungsi AI Assistant meliputi:

- Jelaskan opportunity.
- Ringkas profil institusi.
- Ringkas kebutuhan.
- Buat draft komunikasi.
- Jelaskan alasan scoring.
- Tampilkan risiko utama.
- Sarankan langkah berikutnya.
- Bandingkan beberapa peluang.
- Bantu review rekomendasi.

AI Assistant harus selalu bekerja dalam konteks data yang tersedia.

---

# 22. Reporting Module

Reporting Module menyediakan laporan strategis.

Jenis laporan:

- Opportunity report.
- Institution report.
- Need category report.
- Product gap report.
- Principal opportunity report.
- Data quality report.
- Contactability report.
- Review backlog report.
- Workflow performance report.
- Risk distribution report.

Setiap report harus memiliki definisi data dan filter yang jelas.

---

# 23. Audit Module

Audit Module menampilkan jejak aktivitas sistem dan pengguna.

Audit Module harus mendukung pencarian berdasarkan:

- Entity.
- User.
- Event type.
- Date.
- Status.
- Module.
- Source.
- Risk.
- Configuration version.

Audit Module wajib tersedia untuk menjaga kepercayaan sistem.

---

# 24. Configuration Module

Configuration Module digunakan untuk mengelola aturan aplikasi.

Area konfigurasi:

- Scoring.
- Risk threshold.
- Need categories.
- Product categories.
- Mapping rules.
- Workflow rules.
- Approval policy.
- AI prompt policy.
- Export policy.
- User roles.

Configuration Module harus dibatasi untuk role tertentu.

---

# 25. User Role dalam Aplikasi

Peran pengguna awal:

## 25.1 Owner

Memiliki akses penuh terhadap sistem, konfigurasi strategis, dan audit.

## 25.2 Admin

Mengelola konfigurasi operasional, user, dan data tertentu.

## 25.3 Analyst

Menganalisis opportunity, memberi catatan, dan menyiapkan rekomendasi.

## 25.4 Reviewer

Meninjau dan menyetujui rekomendasi tertentu.

## 25.5 Operator

Menjalankan proses operasional yang sudah disetujui.

## 25.6 Viewer

Melihat data dan laporan tanpa mengubah status.

---

# 26. Permission Principle

Setiap permission harus mengikuti prinsip least privilege.

Pengguna hanya boleh melakukan tindakan yang sesuai dengan perannya.

Tindakan sensitif seperti approval, export, configuration change, dan external communication harus dibatasi.

---

# 27. Navigation Architecture

Navigasi aplikasi NovaNusa harus sederhana dan berorientasi keputusan.

Navigasi utama:

1. Dashboard
2. Institutions
3. Needs
4. Products
5. Principals
6. Opportunities
7. Recommendations
8. Workflow
9. Reports
10. Audit
11. Configuration

Setiap halaman utama harus memiliki akses ke detail entity terkait.

---

# 28. Detail Page Architecture

Setiap detail page harus memiliki struktur umum:

1. Header entity.
2. Status.
3. Summary.
4. Evidence.
5. Related entities.
6. Score atau confidence bila relevan.
7. Risk flag.
8. Recommendation.
9. User notes.
10. Workflow action.
11. Audit trail.

Struktur ini menjaga konsistensi pengalaman pengguna.

---

# 29. Search Architecture

Search harus tersedia lintas entitas.

Search minimal mendukung:

- Institution name.
- Region.
- Need keyword.
- Product name.
- Principal name.
- Opportunity ID.
- Package name.
- Contact.
- User note.

Search harus menghasilkan hasil yang dapat ditelusuri ke entity detail.

---

# 30. Filter Architecture

Filter wajib tersedia pada daftar utama.

Filter penting:

- Region.
- Institution type.
- Need category.
- Product category.
- Principal.
- Opportunity score.
- Confidence.
- Risk level.
- Workflow status.
- Review status.
- Approval status.
- Data source.
- Year.

Filter harus membantu pengguna memprioritaskan keputusan.

---

# 31. Evidence View

Evidence View adalah komponen wajib.

Evidence View menampilkan:

- Potongan teks sumber.
- Nama sumber data.
- Tanggal sumber.
- Field asal.
- Entity terkait.
- Confidence.
- Catatan normalisasi.
- Catatan risiko.

Evidence View membuat sistem explainable.

---

# 32. Score Explanation View

Score Explanation View menampilkan rincian skor opportunity.

Harus mencakup:

- Total score.
- Faktor positif.
- Faktor negatif.
- Bobot faktor.
- Confidence.
- Risk factor.
- Data quality impact.
- Version scoring rule.

Skor tidak boleh tampil sebagai angka kosong tanpa konteks.

---

# 33. Risk View

Risk View menampilkan risiko yang perlu diperhatikan pengguna.

Risk View mencakup:

- Risk level.
- Risk category.
- Risk reason.
- Related evidence.
- Suggested review action.
- Status risk.
- User note.

Risk View membantu mencegah kesalahan tindak lanjut.

---

# 34. Review and Approval View

Review and Approval View digunakan untuk validasi manusia.

Komponen yang harus ditampilkan:

- Summary opportunity.
- Evidence.
- Recommendation.
- Product match.
- Confidence.
- Risk.
- AI explanation bila tersedia.
- Action buttons.
- Notes.
- Audit history.

Action yang tersedia:

- Approve.
- Hold.
- Reject.
- Request review.
- Add note.
- Mark follow-up.

---

# 35. AI Interaction Pattern

Interaksi AI dalam aplikasi harus mengikuti pola:

1. Pengguna memilih konteks.
2. Sistem mengambil data relevan.
3. AI menghasilkan output berbasis konteks.
4. Output diberi label AI-generated.
5. Pengguna meninjau output.
6. Pengguna dapat menerima, mengubah, atau menolak.
7. Semua tindakan dicatat.

AI tidak boleh bekerja tanpa konteks data yang jelas.

---

# 36. Draft Communication Architecture

Draft komunikasi dapat dibuat oleh sistem dengan bantuan AI.

Draft harus memiliki:

- Target institution.
- Context need.
- Product recommendation.
- Evidence summary.
- Tone policy.
- Review status.
- Approval status.
- Generated timestamp.
- User editor.
- Final status.

Draft tidak boleh langsung dikirim tanpa approval.

---

# 37. Export Architecture

Export dalam aplikasi harus dikendalikan.

Sebelum export, sistem harus mengetahui:

- Data yang diekspor.
- Filter yang digunakan.
- User yang melakukan.
- Waktu export.
- Tujuan export bila tersedia.
- Apakah approval diperlukan.
- Apakah data mengandung informasi sensitif.

Export event harus masuk audit log.

---

# 38. Notification Architecture

Notification dapat digunakan untuk membantu pengguna memantau pekerjaan.

Notifikasi dapat mencakup:

- Item perlu review.
- Opportunity high priority.
- Data ingestion selesai.
- Error proses.
- Approval diperlukan.
- Follow-up jatuh tempo.
- Risk high ditemukan.
- Configuration changed.

Notification tidak boleh menggantikan dashboard utama.

---

# 39. Application State

Aplikasi harus membedakan beberapa jenis state:

1. Data processing state.
2. Entity state.
3. Opportunity state.
4. Recommendation state.
5. Workflow state.
6. Review state.
7. Approval state.
8. Export state.
9. AI generation state.

State harus eksplisit, tidak tersembunyi dalam teks bebas.

---

# 40. Data Validation in Application

Aplikasi harus melakukan validasi sebelum tindakan penting.

Validasi meliputi:

- Entity exists.
- Status valid.
- User permission valid.
- Required data complete.
- Risk acceptable.
- Approval available.
- Configuration active.
- Evidence available.
- Audit event can be written.

Jika validasi gagal, aplikasi harus menolak tindakan dan menjelaskan alasannya.

---

# 41. Error Handling in Application

Aplikasi harus menampilkan error secara aman.

Error message harus:

- Jelas.
- Tidak menyesatkan.
- Tidak menghapus konteks.
- Tidak membocorkan informasi yang tidak perlu.
- Menyediakan langkah perbaikan bila memungkinkan.

Error harus dicatat untuk audit atau observability.

---

# 42. Application Observability

Aplikasi harus dapat diamati.

Observability mencakup:

- Jumlah data diproses.
- Jumlah opportunity aktif.
- Jumlah review pending.
- Jumlah approval.
- Jumlah hold.
- Jumlah rejected.
- Error rate.
- AI generation status.
- Export activity.
- User activity.
- Data quality status.

Observability membantu menjaga sistem tetap sehat.

---

# 43. Application Performance Principle

Aplikasi harus cukup responsif untuk digunakan dalam analisis harian.

Halaman ringkasan harus ringan.

Halaman detail dapat memuat data lebih lengkap.

Report besar dapat diproses secara terpisah.

Search dan filter harus dirancang agar tidak menghambat kerja pengguna.

---

# 44. Application Extensibility

Aplikasi harus mudah diperluas.

Penambahan domain baru tidak boleh mengharuskan perubahan besar pada seluruh aplikasi.

Ekstensi yang harus didukung:

- Domain baru.
- Kategori baru.
- Produk baru.
- Principal baru.
- Workflow baru.
- Report baru.
- AI task baru.
- Role baru.
- Data source baru.

---

# 45. Application Maintainability

Maintainability dicapai dengan:

- Modul yang jelas.
- Naming yang konsisten.
- Status eksplisit.
- Audit event standar.
- Configuration terpusat.
- Data access terstruktur.
- Separation of concern.
- Dokumentasi arsitektur.
- Testing konseptual berbasis workflow.

Aplikasi yang sulit dijelaskan berarti belum siap menjadi NovaNusa.

---

# 46. Application Boundary

Application Architecture tidak mencakup:

- Detail database schema.
- Endpoint API.
- Framework frontend.
- Framework backend.
- Detail deployment.
- Detail library.
- Detail kode.
- Infrastruktur cloud.
- Desain visual final.

Semua itu akan dibahas dalam dokumen berikutnya.

---

# 47. Keputusan Application Architecture Final

Keputusan final:

1. NovaNusa dibangun sebagai aplikasi modular decision support.
2. Dashboard adalah pusat interaksi pengguna.
3. Opportunity Module adalah modul operasional inti.
4. Need, Product, Principal, dan Institution adalah modul intelligence utama.
5. Recommendation harus explainable.
6. Workflow harus human-in-the-loop.
7. AI hanya menjadi assistance layer.
8. Audit wajib melekat pada seluruh tindakan penting.
9. Configuration harus terkendali dan tercatat.
10. Export dan komunikasi eksternal harus melalui kontrol approval.
11. Aplikasi harus siap diperluas ke domain dan workflow baru.

---

# 48. Penutup

Application Architecture NovaNusa memastikan bahwa sistem tidak hanya menjadi kumpulan fitur, tetapi menjadi aplikasi intelligence yang terstruktur, aman, dapat diaudit, dan siap dikembangkan bertahap.

Aplikasi NovaNusa harus membantu pengguna memahami kebutuhan institusi, menilai peluang, mencocokkan produk dan principal, meninjau rekomendasi, serta mengambil tindakan secara profesional.

Seluruh implementasi aplikasi NovaNusa wajib menjaga konsistensi dengan dokumen ini.

---

**Status Dokumen:** FINAL
