# 07 — NOVANUSA API DESIGN

---

# Status Dokumen

**Status : FINAL**

Dokumen ini merupakan acuan resmi desain API NovaNusa.

Dokumen ini tidak berisi implementasi kode, tetapi mendefinisikan kontrak konseptual API yang akan digunakan oleh backend, frontend, dashboard, modul AI, workflow, reporting, dan integrasi internal NovaNusa.

Dokumen ini mengacu pada:

- `docs/00_PROJECT_CHARTER.md`
- `docs/01_SYSTEM_VISION.md`
- `docs/02_SYSTEM_SCOPE.md`
- `docs/03_DOMAIN_MODEL.md`
- `docs/04_DATA_ARCHITECTURE.md`
- `docs/05_SYSTEM_ARCHITECTURE.md`
- `docs/06_APPLICATION_ARCHITECTURE.md`

---

# 1. Tujuan Dokumen

Dokumen ini bertujuan menetapkan desain API NovaNusa secara resmi.

API Design menjadi kontrak antara:

- Backend application.
- Frontend dashboard.
- Workflow engine.
- Intelligence engine.
- AI assistance layer.
- Reporting module.
- Audit system.
- Configuration module.
- Integrasi internal dan eksternal di masa depan.

Dokumen ini memastikan bahwa seluruh komunikasi antar bagian sistem konsisten, dapat diaudit, aman, dan sesuai domain model NovaNusa.

---

# 2. Prinsip API NovaNusa

API NovaNusa wajib mengikuti prinsip berikut:

1. Domain-first.
2. Consistent.
3. Explainable.
4. Auditable.
5. Human-in-the-loop.
6. Safe by default.
7. Versioned.
8. Predictable.
9. Filterable.
10. Extensible.

API tidak boleh hanya mengejar kecepatan implementasi.

API harus menjadi kontrak jangka panjang sistem NovaNusa.

---

# 3. Karakter API

API NovaNusa dirancang sebagai API berbasis resource dan action.

Resource digunakan untuk entitas domain utama, seperti:

- Institutions
- Needs
- Products
- Principals
- Opportunities
- Recommendations
- Contacts
- Reports
- Audit Logs
- Configurations

Action digunakan untuk tindakan workflow, seperti:

- Review
- Approve
- Hold
- Reject
- Generate recommendation
- Generate AI summary
- Export
- Reprocess

Resource API harus menjaga konsistensi data.

Action API harus mencatat audit event.

---

# 4. API Versioning

API NovaNusa harus memiliki versioning.

Versi awal menggunakan pola konseptual:

`/api/v1`

Contoh:

- `/api/v1/institutions`
- `/api/v1/opportunities`
- `/api/v1/recommendations`
- `/api/v1/workflows`
- `/api/v1/audit-logs`

Versioning diperlukan agar perubahan di masa depan tidak merusak aplikasi yang sudah berjalan.

Perubahan besar pada struktur response, nama field utama, atau workflow harus menggunakan versi baru.

---

# 5. Standar Response API

Setiap response API harus konsisten.

Struktur umum response sukses:

```json
{
  "success": true,
  "data": {},
  "meta": {},
  "audit": {}
}

Struktur umum response error:

{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {}
  },
  "meta": {},
  "audit": {}
}

Response tidak boleh ambigu.

Jika terjadi error, API harus menjelaskan penyebab secara aman dan tidak menyesatkan.

6. Standar Metadata

Field meta digunakan untuk informasi tambahan.

Metadata dapat mencakup:

Pagination.
Filter yang digunakan.
Search keyword.
Sort order.
Data version.
Rule version.
Generated timestamp.
Processing status.
Request ID.

Contoh metadata:

{
  "meta": {
    "page": 1,
    "page_size": 25,
    "total_items": 250,
    "total_pages": 10,
    "sort": "score_desc",
    "generated_at": "timestamp"
  }
}

Metadata membantu dashboard memahami konteks response.

7. Standar Audit Context

API penting harus mengembalikan audit context.

Field audit dapat mencakup:

Request ID.
Actor.
Action.
Entity type.
Entity ID.
Timestamp.
Audit event ID.
Source reference.

Contoh:

{
  "audit": {
    "request_id": "REQ-0001",
    "event_id": "AUD-0001",
    "actor": "system_or_user",
    "action": "opportunity.approved",
    "timestamp": "timestamp"
  }
}

Audit context wajib untuk action API.

8. Authentication dan Authorization

API NovaNusa harus mendukung authentication dan authorization.

Authentication menjawab:

Siapa pengguna yang mengakses sistem?

Authorization menjawab:

Apa yang boleh dilakukan pengguna tersebut?

Role awal:

Owner
Admin
Analyst
Reviewer
Operator
Viewer

API harus memeriksa permission sebelum tindakan penting.

Tindakan seperti approval, export, configuration change, dan external communication wajib dibatasi berdasarkan role.

9. Permission Model API

Permission API harus mengikuti prinsip least privilege.

Contoh permission:

institution.read
need.read
product.read
opportunity.read
opportunity.review
opportunity.approve
recommendation.read
recommendation.approve
workflow.update
report.read
audit.read
configuration.update
export.create

Setiap action penting harus memeriksa permission secara eksplisit.

10. Pagination

Endpoint list harus mendukung pagination.

Parameter standar:

page
page_size

Contoh:

GET /api/v1/opportunities?page=1&page_size=25

Pagination response harus mencakup:

Current page.
Page size.
Total items.
Total pages.
Has next.
Has previous.

Pagination wajib untuk data besar seperti opportunities, institutions, needs, dan audit logs.

11. Sorting

Endpoint list harus mendukung sorting.

Parameter standar:

sort

Contoh:

sort=score_desc
sort=created_at_desc
sort=risk_level_desc
sort=name_asc

Sorting harus terdokumentasi per endpoint.

Sorting default harus aman dan masuk akal.

12. Filtering

Endpoint list harus mendukung filtering berdasarkan domain.

Filter umum:

status
region
category
risk_level
confidence
source
year
principal
product_category
workflow_status
review_status
approval_status

Contoh:

GET /api/v1/opportunities?status=review_required&risk_level=medium

Filter harus membantu dashboard dan analyst memprioritaskan pekerjaan.

13. Search

Search harus mendukung pencarian lintas entitas.

Endpoint search konseptual:

GET /api/v1/search?q=keyword

Search harus dapat mencari:

Institution name.
Need keyword.
Product name.
Principal name.
Opportunity ID.
Package name.
Contact.
User note.

Search response harus mencantumkan tipe entitas agar pengguna dapat membuka detail yang tepat.

14. Error Model

API harus menggunakan error code yang konsisten.

Kategori error:

VALIDATION_ERROR
AUTHENTICATION_REQUIRED
PERMISSION_DENIED
RESOURCE_NOT_FOUND
CONFLICT
INVALID_WORKFLOW_TRANSITION
APPROVAL_REQUIRED
RISK_REVIEW_REQUIRED
DATA_QUALITY_INSUFFICIENT
AI_CONTEXT_MISSING
EXPORT_NOT_ALLOWED
INTERNAL_ERROR

Error message harus jelas dan aman.

API tidak boleh menyembunyikan kegagalan tindakan penting.

15. Institution API

Institution API mengelola akses ke data institusi.

Endpoint konseptual:

GET /api/v1/institutions
GET /api/v1/institutions/{institution_id}
GET /api/v1/institutions/{institution_id}/needs
GET /api/v1/institutions/{institution_id}/opportunities
GET /api/v1/institutions/{institution_id}/contacts
GET /api/v1/institutions/{institution_id}/audit-logs

Institution detail harus menampilkan:

Identity.
Region.
Institution type.
Needs.
Opportunities.
Contacts.
Recommendations.
Risk flags.
Data quality.
Audit summary.
16. Need API

Need API mengelola kebutuhan yang terdeteksi.

Endpoint konseptual:

GET /api/v1/needs
GET /api/v1/needs/{need_id}
GET /api/v1/needs/{need_id}/evidence
GET /api/v1/needs/{need_id}/products
GET /api/v1/needs/{need_id}/opportunities
POST /api/v1/needs/{need_id}/review

Need response harus mencakup:

Need label.
Need category.
Institution.
Source package.
Evidence.
Confidence.
Risk flag.
Review status.
17. Product API

Product API mengelola produk dan solusi.

Endpoint konseptual:

GET /api/v1/products
GET /api/v1/products/{product_id}
GET /api/v1/products/{product_id}/needs
GET /api/v1/products/{product_id}/opportunities
GET /api/v1/products/{product_id}/principals
POST /api/v1/products/{product_id}/review

Product response harus mencakup:

Product name.
Product category.
Principal.
Specification summary.
Source.
Version.
Matching notes.
Risk flags.
18. Principal API

Principal API mengelola principal.

Endpoint konseptual:

GET /api/v1/principals
GET /api/v1/principals/{principal_id}
GET /api/v1/principals/{principal_id}/products
GET /api/v1/principals/{principal_id}/opportunities
GET /api/v1/principals/{principal_id}/gaps

Principal response harus membantu pengguna melihat hubungan supply dan demand.

19. Opportunity API

Opportunity API adalah API inti NovaNusa.

Endpoint konseptual:

GET /api/v1/opportunities
GET /api/v1/opportunities/{opportunity_id}
GET /api/v1/opportunities/{opportunity_id}/evidence
GET /api/v1/opportunities/{opportunity_id}/score
GET /api/v1/opportunities/{opportunity_id}/recommendations
GET /api/v1/opportunities/{opportunity_id}/audit-logs
POST /api/v1/opportunities/{opportunity_id}/review
POST /api/v1/opportunities/{opportunity_id}/approve
POST /api/v1/opportunities/{opportunity_id}/hold
POST /api/v1/opportunities/{opportunity_id}/reject
POST /api/v1/opportunities/{opportunity_id}/follow-up

Opportunity detail harus mencakup:

Institution.
Need.
Product match.
Principal match.
Budget context.
Score.
Score explanation.
Confidence.
Risk level.
Recommendation.
Workflow status.
Evidence.
User notes.
Audit trail.
20. Recommendation API

Recommendation API mengelola rekomendasi sistem.

Endpoint konseptual:

GET /api/v1/recommendations
GET /api/v1/recommendations/{recommendation_id}
POST /api/v1/recommendations/{recommendation_id}/review
POST /api/v1/recommendations/{recommendation_id}/approve
POST /api/v1/recommendations/{recommendation_id}/hold
POST /api/v1/recommendations/{recommendation_id}/reject
GET /api/v1/recommendations/{recommendation_id}/evidence
GET /api/v1/recommendations/{recommendation_id}/audit-logs

Recommendation response harus mencakup:

Related opportunity.
Related need.
Related product.
Reasoning.
Evidence.
Confidence.
Risk.
Suggested action.
Review status.
Approval status.
21. Workflow API

Workflow API mengatur perubahan status.

Endpoint konseptual:

GET /api/v1/workflows/statuses
GET /api/v1/workflows/queues
GET /api/v1/workflows/review-required
GET /api/v1/workflows/approved
GET /api/v1/workflows/hold
POST /api/v1/workflows/transition

Workflow transition request harus mencakup:

Entity type.
Entity ID.
Current status.
Target status.
Reason.
User note.

Workflow API harus menolak transisi yang tidak valid.

22. Review API

Review API digunakan untuk validasi manusia.

Endpoint konseptual:

GET /api/v1/reviews
GET /api/v1/reviews/{review_id}
POST /api/v1/reviews/{review_id}/submit
POST /api/v1/reviews/{review_id}/request-changes

Review harus mencatat:

Reviewer.
Entity reviewed.
Decision.
Notes.
Timestamp.
Risk context.
Evidence checked.
23. Approval API

Approval API digunakan untuk tindakan formal.

Endpoint konseptual:

GET /api/v1/approvals
GET /api/v1/approvals/pending
POST /api/v1/approvals/{approval_id}/approve
POST /api/v1/approvals/{approval_id}/reject

Approval response harus mencakup:

Approval status.
Approved by.
Approved at.
Entity approved.
Reason.
Audit event.

Approval wajib untuk tindakan eksternal dan perubahan status penting.

24. AI API

AI API menyediakan bantuan berbasis AI.

Endpoint konseptual:

POST /api/v1/ai/summarize-institution
POST /api/v1/ai/summarize-need
POST /api/v1/ai/explain-opportunity
POST /api/v1/ai/explain-score
POST /api/v1/ai/generate-draft
POST /api/v1/ai/check-risk
POST /api/v1/ai/compare-opportunities

AI request harus mencakup context ID, bukan hanya teks bebas.

AI response harus mencakup:

Output.
Context used.
Source references.
Confidence note.
Limitation note.
Review required flag.
Audit event.

AI API tidak boleh digunakan untuk membuat fakta baru tanpa basis data.

25. Reporting API

Reporting API menyediakan laporan strategis.

Endpoint konseptual:

GET /api/v1/reports/opportunities
GET /api/v1/reports/institutions
GET /api/v1/reports/needs
GET /api/v1/reports/products
GET /api/v1/reports/principals
GET /api/v1/reports/data-quality
GET /api/v1/reports/contactability
GET /api/v1/reports/risk
GET /api/v1/reports/workflow

Report response harus mencantumkan:

Definition.
Filters.
Generated time.
Data source.
Aggregation method.
Result.

Tidak boleh ada report tanpa definisi metrik yang jelas.

26. Audit Log API

Audit Log API menyediakan akses ke jejak sistem.

Endpoint konseptual:

GET /api/v1/audit-logs
GET /api/v1/audit-logs/{audit_event_id}
GET /api/v1/audit-logs/by-entity/{entity_type}/{entity_id}
GET /api/v1/audit-logs/by-user/{user_id}

Audit log response harus mencakup:

Event ID.
Event type.
Actor.
Entity type.
Entity ID.
Previous value.
New value.
Timestamp.
Source.
Notes.

Audit API harus dibatasi berdasarkan role.

27. Configuration API

Configuration API mengelola aturan sistem.

Endpoint konseptual:

GET /api/v1/configurations
GET /api/v1/configurations/{config_key}
POST /api/v1/configurations/{config_key}/propose-change
POST /api/v1/configurations/{config_key}/approve-change
GET /api/v1/configurations/{config_key}/versions

Configuration change harus melalui audit dan approval bila berdampak besar.

28. Export API

Export API mengatur ekspor data.

Endpoint konseptual:

POST /api/v1/exports/opportunities
POST /api/v1/exports/institutions
POST /api/v1/exports/recommendations
POST /api/v1/exports/reports
GET /api/v1/exports/{export_id}

Export request harus mencakup:

Export type.
Filter.
Format.
Purpose.
Approval reference bila diperlukan.

Export harus tercatat di audit log.

29. Contact API

Contact API mengelola contact intelligence.

Endpoint konseptual:

GET /api/v1/contacts
GET /api/v1/contacts/{contact_id}
GET /api/v1/contacts/by-institution/{institution_id}
POST /api/v1/contacts/{contact_id}/review
POST /api/v1/contacts/{contact_id}/mark-valid
POST /api/v1/contacts/{contact_id}/mark-invalid

Contact response harus mencakup:

Contact value.
Contact type.
Institution.
Source.
Confidence.
Validity status.
Last checked.
Risk flag.
30. Data Quality API

Data Quality API mendukung penilaian kualitas data.

Endpoint konseptual:

GET /api/v1/data-quality/summary
GET /api/v1/data-quality/institutions
GET /api/v1/data-quality/needs
GET /api/v1/data-quality/products
GET /api/v1/data-quality/contacts
GET /api/v1/data-quality/issues
POST /api/v1/data-quality/issues/{issue_id}/resolve

Data quality response harus mencakup:

Completeness.
Consistency.
Freshness.
Traceability.
Validity.
Risk level.
Suggested action.
31. Reprocessing API

Reprocessing API digunakan untuk memproses ulang data.

Endpoint konseptual:

POST /api/v1/reprocessing/needs
POST /api/v1/reprocessing/products
POST /api/v1/reprocessing/opportunities
POST /api/v1/reprocessing/recommendations
GET /api/v1/reprocessing/jobs/{job_id}

Reprocessing request harus mencakup:

Scope.
Reason.
Rule version.
User.
Approval reference bila diperlukan.

Reprocessing tidak boleh menghapus riwayat hasil lama tanpa audit.

32. Notification API

Notification API mendukung pemberitahuan internal.

Endpoint konseptual:

GET /api/v1/notifications
POST /api/v1/notifications/{notification_id}/read
POST /api/v1/notifications/{notification_id}/dismiss

Notification dapat berisi:

Review required.
High risk.
Approval needed.
Processing completed.
Export ready.
Data quality issue.
Configuration changed.
33. Dashboard API

Dashboard API menyediakan ringkasan untuk UI utama.

Endpoint konseptual:

GET /api/v1/dashboard/overview
GET /api/v1/dashboard/opportunity-summary
GET /api/v1/dashboard/risk-summary
GET /api/v1/dashboard/review-queue
GET /api/v1/dashboard/data-quality-summary
GET /api/v1/dashboard/recent-activity

Dashboard API harus ringan dan cepat.

Detail mendalam tetap diambil dari endpoint domain masing-masing.

34. Standard Entity Reference

Untuk menjaga konsistensi, API harus menggunakan entity reference standar.

Contoh entity reference:

{
  "entity_type": "opportunity",
  "entity_id": "OPP-0001",
  "display_name": "Pengadaan perangkat IT - Dinas X"
}

Entity reference digunakan pada audit, workflow, recommendation, AI, dan notification.

35. Standard Evidence Object

Evidence object harus memiliki struktur standar.

Contoh:

{
  "evidence_id": "EVD-0001",
  "source_name": "source",
  "source_type": "procurement_package",
  "source_field": "description",
  "text": "evidence text",
  "confidence": 0.87,
  "created_at": "timestamp"
}

Evidence wajib tersedia untuk need detection, product mapping, scoring, dan recommendation.

36. Standard Risk Object

Risk object harus memiliki struktur standar.

Contoh:

{
  "risk_level": "medium",
  "risk_category": "product_mismatch",
  "reason": "Product category partially matches need category",
  "suggested_action": "Manual review required"
}

Risk object membantu dashboard menampilkan risiko secara konsisten.

37. Standard Score Object

Score object harus memiliki struktur standar.

Contoh:

{
  "score": 82,
  "score_level": "high",
  "breakdown": [
    {
      "factor": "need_relevance",
      "value": 30,
      "reason": "Need strongly matches product category"
    }
  ],
  "rule_version": "v1"
}

Score harus explainable dan versioned.

38. Standard Workflow Action Object

Workflow action harus memiliki struktur standar.

Contoh:

{
  "entity_type": "opportunity",
  "entity_id": "OPP-0001",
  "action": "approve",
  "reason": "Relevant and ready for follow-up",
  "note": "Reviewed by analyst"
}

Workflow action wajib menghasilkan audit event.

39. Standard AI Output Object

AI output harus memiliki struktur standar.

Contoh:

{
  "output": "AI generated explanation",
  "context_used": [],
  "source_references": [],
  "limitations": [],
  "review_required": true
}

AI output tidak boleh dianggap final sebelum review bila digunakan untuk tindakan penting.

40. API Safety Rules

API NovaNusa harus menerapkan aturan keselamatan berikut:

Tidak ada external action tanpa approval.
Tidak ada approval tanpa permission.
Tidak ada recommendation tanpa evidence.
Tidak ada AI output tanpa context.
Tidak ada status change tanpa audit.
Tidak ada export tanpa audit.
Tidak ada configuration change tanpa versioning.
Tidak ada entity merge tanpa traceability.
Tidak ada scoring tanpa rule version.
Tidak ada deletion permanen tanpa governance.
41. Delete Policy API

API tidak boleh melakukan hard delete secara default.

Penghapusan harus menggunakan pendekatan:

Archive.
Mark inactive.
Soft delete.
Superseded by version.

Hard delete hanya boleh dilakukan untuk kasus khusus yang disetujui governance.

Data yang berkaitan dengan audit tidak boleh dihapus sembarangan.

42. API Naming Convention

API harus menggunakan penamaan yang konsisten.

Prinsip:

Resource menggunakan plural noun.
Action menggunakan verb yang jelas.
Field menggunakan nama eksplisit.
Status menggunakan enum standar.
ID menggunakan format konsisten.
Response menggunakan struktur standar.

Contoh resource:

/institutions
/needs
/products
/principals
/opportunities
/recommendations

Contoh action:

/approve
/hold
/reject
/review
/generate-draft
43. API Status Enum

Status workflow utama:

new
processed
matched
scored
recommended
review_required
approved
hold
rejected
follow_up
completed
archived

Risk level:

low
medium
high
critical

Confidence level:

low
medium
high

Review status:

not_reviewed
in_review
reviewed
changes_requested

Approval status:

not_required
pending
approved
rejected
44. API Observability

API harus mendukung observability.

Hal yang perlu dipantau:

Request count.
Error count.
Response time.
Failed workflow transition.
Failed approval.
AI generation failure.
Export activity.
Reprocessing job.
Data quality issue.
Permission denial.

Observability membantu menjaga sistem tetap stabil dan aman.

45. API Documentation Standard

Setiap endpoint harus memiliki dokumentasi minimal:

Endpoint path.
Method.
Purpose.
Required permission.
Request parameter.
Request body.
Response body.
Error codes.
Audit behavior.
Notes.

Dokumentasi API harus diperbarui ketika kontrak API berubah.

46. API Boundary

Dokumen ini tidak menentukan:

Framework backend.
Bahasa pemrograman.
Library API.
Database driver.
Detail deployment.
Struktur folder kode.
Implementasi authentication teknis.
Implementasi caching.
Implementasi queue.

Hal-hal tersebut akan ditentukan pada dokumen teknis berikutnya.

47. Keputusan API Design Final

Keputusan final API NovaNusa:

API menggunakan versioning /api/v1.
API berbasis resource dan action.
Response API harus konsisten.
Endpoint list wajib mendukung pagination, filtering, sorting, dan search bila relevan.
Opportunity API menjadi inti operasional.
Workflow, review, approval, audit, dan AI memiliki endpoint khusus.
AI API harus context-based dan reviewable.
Export API harus audited.
Configuration API harus versioned.
Tidak ada tindakan penting tanpa permission dan audit.
Tidak ada rekomendasi tanpa evidence.
Tidak ada tindakan eksternal tanpa approval manusia.
48. Penutup

API Design NovaNusa memastikan bahwa seluruh modul sistem dapat berkomunikasi secara konsisten, aman, explainable, dan auditable.

API bukan hanya jalur teknis, tetapi kontrak resmi yang menjaga agar aplikasi, dashboard, AI, workflow, data, dan audit tetap berada dalam satu fondasi yang sama.

Seluruh implementasi API NovaNusa wajib menjaga konsistensi dengan dokumen ini.

Status Dokumen: FINAL
