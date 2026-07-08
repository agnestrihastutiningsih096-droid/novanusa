# NOVANUSA DASHBOARD SPECIFICATION v1

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan tetap untuk penyusunan Dashboard NovaNusa v1.

Dashboard NovaNusa bukan sekadar dashboard email, melainkan pusat kerja Enterprise Procurement Intelligence yang menghubungkan institusi, kebutuhan, principal, produk, peluang, outreach, dan knowledge.

---

# Prinsip Utama Dashboard

Dashboard NovaNusa dibangun berdasarkan alur utama:

Institution

↓

Need

↓

Opportunity

↓

Principal

↓

Product

↓

Outreach

↓

Follow Up

↓

Deal

Email bukan pusat sistem.

Email hanyalah salah satu aktivitas dalam proses opportunity management.

---

# Struktur Navigasi Final

NovaNusa memiliki struktur menu sebagai berikut:

## 1. Home

Ringkasan kondisi enterprise.

Menampilkan:

- Total institutions
- Total SiRUP needs
- Total opportunities
- Total principals
- Total products
- Email ready
- Email sent
- Follow up pending
- Estimated opportunity value

---

## 2. Opportunities

Workspace utama untuk mengelola peluang.

Submenu:

- Pipeline
- Kanban
- Opportunity List
- Opportunity Detail
- Analytics

Status opportunity:

- Need Detected
- Need Reviewed
- Principal Matched
- Product Matched
- Email Drafted
- Approved
- Sent
- Follow Up
- Negotiation
- Won
- Lost
- Hold

---

## 3. Institutions

Workspace utama untuk melihat instansi.

Submenu:

- All Institutions
- Institution Profile
- Contacts
- Government Map
- Institution History

Institution Profile wajib menjadi halaman inti.

Urutan halaman Institution Profile:

1. Institution Summary
2. Contact Information
3. SiRUP Original Data
4. Need Timeline
5. Need Analysis
6. Opportunity List
7. Matched Principals
8. Matched Products
9. Outreach History
10. Follow Up Timeline
11. Knowledge Notes
12. Activity History

Data asli SiRUP tidak boleh diubah.

Analisis NovaNusa harus ditampilkan terpisah dari data asli SiRUP.

---

## 4. Needs

Workspace untuk membaca kebutuhan pasar pemerintah.

Submenu:

- Need Explorer
- Need Domains
- SiRUP Packages
- Need Trend
- Gap Opportunity

Need Domains minimal:

- IT Hardware
- Networking
- CCTV
- Audio Video
- Camera
- Drone
- Office Equipment
- Furniture
- Medical Device
- Laboratory
- Radiology
- Dental
- Education
- Construction
- Security
- Other

Need Explorer harus bisa difilter berdasarkan:

- Tahun
- Provinsi
- Kabupaten/Kota
- KLD
- Jenis instansi
- Domain kebutuhan
- Pagu
- Status matching
- Status contact
- Status outreach

---

## 5. Principals

Workspace Business Development.

Submenu:

- Principal Directory
- Principal Profile
- Product Catalog
- Coverage
- Partnership Status
- Gap Need

Principal Profile menampilkan:

- Nama principal
- Brand
- Domain
- Produk
- Coverage wilayah
- Status kerja sama
- Opportunity terkait
- Gap produk
- Catatan hubungan

---

## 6. Products

Workspace katalog produk.

Submenu:

- Product Catalog
- Product Matching
- Product Gap
- Principal Products

Setiap produk wajib terhubung dengan:

- Principal
- Domain kebutuhan
- Opportunity
- Institution
- Status kecocokan

---

## 7. AI Intelligence

Workspace analisis.

Submenu:

- Matching
- Opportunity Score
- Recommendation
- Explainability
- Knowledge

AI Intelligence harus menjelaskan alasan rekomendasi, bukan hanya memberi hasil.

Setiap rekomendasi harus memiliki:

- dasar kebutuhan
- data sumber
- alasan kecocokan
- tingkat confidence
- risiko atau catatan
- rekomendasi tindakan

---

## 8. Outreach

Workspace komunikasi.

Submenu:

- Email Drafts
- Outbox
- Sent Emails
- Follow Up
- Campaigns

Outreach mengikuti status:

- Draft
- Review
- Approved
- Sent
- Follow Up
- Replied
- Meeting
- Closed

Setiap email harus terhubung ke:

- Institution
- Need
- Opportunity
- Principal
- Product
- Campaign

---

## 9. Analytics

Workspace analitik enterprise.

Menampilkan:

- Opportunity by domain
- Opportunity by province
- Opportunity by institution type
- Opportunity by principal
- Opportunity by product category
- Outreach performance
- Follow up performance
- Gap opportunity
- Estimated value

---

## 10. Knowledge

Workspace catatan dan pengetahuan.

Menampilkan:

- Institution knowledge
- Principal knowledge
- Product knowledge
- Need knowledge
- Decision history
- Notes
- Lessons learned

---

## 11. Administration

Workspace administratif.

Menampilkan:

- Import data
- Data validation
- Contact management
- User role
- Review queue
- Audit history

---

## 12. Settings

Pengaturan umum dashboard.

Menampilkan:

- Domain setting
- Principal setting
- Product setting
- Outreach setting
- Dashboard preference

---

# Halaman Paling Penting v1

Untuk versi fixed pertama, halaman yang wajib selesai adalah:

1. Home
2. Opportunities
3. Institutions
4. Institution Profile
5. Needs
6. Principals
7. Outreach

Halaman lain dapat menyusul setelah dashboard utama stabil.

---

# Fokus Bisnis Hari Ini

Dashboard v1 harus mampu menjawab pertanyaan berikut:

1. Instansi mana yang memiliki kebutuhan?
2. Kebutuhannya apa?
3. Data asli SiRUP-nya apa?
4. Apakah ada principal yang cocok?
5. Produk apa yang bisa ditawarkan?
6. Apakah kontak tersedia?
7. Apakah email sudah siap?
8. Apakah sudah dikirim?
9. Apa tindak lanjut berikutnya?
10. Di mana peluang yang belum punya principal?

---

# Skenario Demo Mitracom

Untuk Mitracom, dashboard harus bisa menunjukkan:

- instansi target
- kebutuhan IT Hardware
- kebutuhan printer/scanner
- kebutuhan networking
- data asli SiRUP
- produk Mitracom yang cocok
- draft email
- status pengiriman
- follow up

---

# Skenario Demo Alat Kesehatan

Untuk alat kesehatan, dashboard harus bisa menunjukkan:

- kebutuhan Medical Device
- kebutuhan Laboratory
- kebutuhan Radiology
- kebutuhan Dental
- instansi kesehatan
- nilai pagu
- lokasi
- gap principal
- peluang kerja sama dengan principal alat kesehatan

---

# Keputusan Final

Dashboard NovaNusa v1 menggunakan pendekatan Entity Driven.

Objek utama dashboard adalah:

- Institution
- Need
- Opportunity
- Principal
- Product
- Outreach
- Knowledge

Seluruh menu, filter, analitik, dan workflow harus mengikuti struktur tersebut.

Dashboard ini menjadi fondasi operasional NovaNusa untuk Mitracom, alat kesehatan, dan principal lain di masa depan.

---

**Status Dokumen:** FINAL
