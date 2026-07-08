# 17. Procurement Data Inventory

## 1. Objective

NovaNusa needs a procurement data inventory because SiRUP alone is not enough to determine the real lifecycle status of a government procurement package.

SiRUP, the Sistem Informasi Rencana Umum Pengadaan, is primarily a planning and publication system for planned procurement packages. It helps answer what a government institution planned to buy, the approximate budget, the planned procurement method, the work unit, and the planned selection month. It does not prove that a package is still open, tendered, awarded, contracted, delivered, paid, cancelled, or completed.

A package can move through multiple public systems after it appears in SiRUP: SPSE/LPSE, e-purchasing/katalog, winner announcements, contract publications, PPID documents, audit reports, and statistical portals. NovaNusa must treat SiRUP as the planning layer and connect it to downstream public evidence before assigning factual lifecycle status.

Lifecycle:

Planning -> Announcement -> Tender / Non Tender -> Winner -> Contract -> Delivery -> Payment -> Completion

Architecture rule: lifecycle status must be evidence-based. If no downstream public evidence is available locally, the correct statement is not "still open"; it is "no public match found in available evidence sources."

## 2. Procurement Lifecycle

### Planning

Purpose: publish the buyer's planned procurement need, budget, method, work unit, and planned timing.

Responsible institution: the procuring K/L/PD or work unit publishes the plan; LKPP operates SiRUP.

Available public data: RUP records, package name, budget, planned method, KLDI, satker/work unit, location, funding source, planned month.

Typical identifiers: RUP ID, package/reference ID where present, KLDI ID, satker ID, KLDI name, work unit name, package name, budget, fiscal year, planned month.

### Announcement

Purpose: make a procurement process publicly visible for suppliers and public monitoring.

Responsible institution: procurement working group, UKPBJ/ULP, LPSE operators, and related K/L/PD procurement administrators.

Available public data: tender/non-tender announcement pages, package details, schedules, requirements, procurement method, HPS/ceiling where published, tender ID, package ID, institution, LPSE source.

Typical identifiers: tender ID, LPSE package ID, package name, RUP ID if linked, institution, work unit, budget/HPS, fiscal year, SPSE/LPSE URL.

### Tender / Non Tender

Purpose: record active procurement execution such as registration, document download, qualification, bidding, evaluation, clarification, and sanggah phases.

Responsible institution: procurement working group, UKPBJ/ULP, LPSE operator, and buyer work unit.

Available public data: SPSE/LPSE process pages, schedules, participants, evaluation stages, status messages, addendum notices, and method.

Typical identifiers: tender ID, non-tender ID, package name, LPSE URL, RUP ID if linked, KLDI, satker, method, HPS, schedule stage.

### Winner

Purpose: identify selected supplier/provider after evaluation and award.

Responsible institution: procurement working group and buyer institution, usually published through SPSE/LPSE where available.

Available public data: winner announcement, supplier name, bid value, corrected bid value, ranking, announcement date, and tender/non-tender reference.

Typical identifiers: tender ID, package ID, supplier name, provider ID where public, package name, winner value, announcement date, LPSE URL.

### Contract

Purpose: prove that an award became a legal procurement commitment.

Responsible institution: buyer institution, PPK/contracting officer, procurement unit, and sometimes SPSE/LPSE or agency publication channels.

Available public data: contract status, contract number if published, contract value, supplier, contract date, "pemenang berkontrak" status, procurement result summaries, PPID reports.

Typical identifiers: contract number, tender ID, package ID, RUP ID if linked, supplier name, contract value, contract date, work unit, package name.

### Delivery

Purpose: record whether goods/services were delivered or work was performed.

Responsible institution: buyer work unit, PPK, supplier, receiving committee, and asset/user unit.

Available public data: less consistently public; may appear in BAST summaries, asset reports, contract implementation reports, agency reports, press releases, PPID documents, or audits.

Typical identifiers: contract number, package name, supplier, delivery date, BAST number, asset/service description, work unit.

### Payment

Purpose: record disbursement against a procurement or contract.

Responsible institution: buyer finance unit, treasury systems, Ministry of Finance systems for central government, regional finance systems for local government.

Available public data: often not fully public at package granularity; aggregate budget realization or procurement realization may appear in reports, PPID, APBD/APBN reporting, or open data portals.

Typical identifiers: contract number, payment reference, supplier, budget account, realization amount, fiscal year, work unit.

### Completion

Purpose: record final lifecycle state: completed, cancelled, failed, closed, or otherwise ended.

Responsible institution: procurement working group, PPK, buyer institution, LPSE/SPSE, and audit/reporting bodies.

Available public data: SPSE/LPSE final status, failed/cancelled/batal status, winner/contract records, procurement realization reports, audit summaries, PPID documents.

Typical identifiers: tender ID, package ID, RUP ID if linked, contract number, supplier, package name, final status, completion date.

## 3. Public Data Sources

### SiRUP

Official name: Sistem Informasi Rencana Umum Pengadaan.

Official website: `https://sirup.lkpp.go.id/`

Managing institution: LKPP.

Purpose: publishes government procurement planning data.

Public availability: public search and package-level access are available. Bulk/API availability should be verified before integration.

Download format: HTML public views; CSV/Excel/API/JSON availability depends on official export/API access or local/manual exports.

Update frequency: frequent during planning and revision periods; treat as daily or near-daily for operational sync if permitted.

Main identifiers: RUP ID, package/reference ID, KLDI ID, satker ID, KLDI name, work unit, package name, pagu, fiscal year, planned month, procurement method.

Relevant columns: RUP ID, id_referensi/package reference, paket, pagu, satuanKerja, kldi, lokasi, metode, jenisPengadaan, sumberDana, idBulan, pemilihan, idKldi, idSatker.

Typical limitations: planning-only; does not prove tender, award, contract, delivery, payment, or completion. Package names may change downstream.

Potential legal/licensing concerns: use as public procurement transparency data; respect LKPP terms, robots.txt, rate limits, and official access patterns.

How it relates to SiRUP: this is the planning anchor dataset.

Priority for NovaNusa integration: Phase 1.

### SPSE Nasional

Official name: Sistem Pengadaan Secara Elektronik Nasional / SPSE Nasional.

Official website: `https://spse.inaproc.id/`

Managing institution: LKPP and the national SPSE/INAPROC ecosystem.

Purpose: provides national discovery/search access for electronic procurement processes across SPSE/LPSE infrastructure.

Public availability: public search and package pages are generally available. Bulk download/API access should be verified and not assumed.

Download format: primarily HTML; CSV/Excel may be available only through specific export features, manual downloads, or future official facilities. JSON/API availability is uncertain.

Update frequency: frequent; active tender stage data can change daily or more often.

Main identifiers: tender ID, package ID, package name, LPSE, KLDI, satker/work unit, HPS/pagu, method, schedule, status.

Relevant columns: tender code, package name, agency, work unit, method, HPS, schedule/tahapan, status, LPSE source, source URL, RUP ID if shown.

Typical limitations: search results may not expose every field; historical records may require LPSE-specific pages; package names can differ from SiRUP.

Potential legal/licensing concerns: use only public data; do not bypass access controls; prefer manual exports or official APIs if provided.

How it relates to SiRUP: downstream evidence for announcement, tender/non-tender process, winner, cancellation/failure, and sometimes contract status.

Priority for NovaNusa integration: Phase 1.

### LPSE

Official name: Layanan Pengadaan Secara Elektronik.

Official website: distributed across national, ministry, provincial, city, regency, and institutional LPSE domains.

Managing institution: each LPSE is operated by the relevant government institution or regional procurement service, using the SPSE system coordinated in the LKPP ecosystem.

Purpose: hosts tender/non-tender records for specific institutions or regions.

Public availability: public package pages and tender data are generally available; export availability varies.

Download format: HTML is common. CSV/Excel may be available from manual exports or reports. PDF may appear in specific contexts. API/JSON availability is uncertain.

Update frequency: frequent during active procurement processes.

Main identifiers: tender ID, package ID, RUP ID if linked, LPSE name, KLDI, satker, package name, HPS, method, status, schedule, winner.

Relevant columns: package name, tender code, stage, HPS, procurement method, procurement category, agency, work unit, qualification, participants, winner, bid value, contract status, source URL.

Typical limitations: fragmented domains, layout differences by SPSE version, inconsistent historical access, and manual download needs.

Potential legal/licensing concerns: respect robots.txt and terms of use; do not bypass authentication or CAPTCHAs.

How it relates to SiRUP: primary execution evidence after planning.

Priority for NovaNusa integration: Phase 1.

### INAPROC

Official name: INAPROC / Portal Pengadaan Nasional.

Official website: `https://inaproc.id/`

Managing institution: LKPP.

Purpose: national procurement portal and entry point for procurement services and information.

Public availability: public portal exists; exact data products and export capabilities should be verified.

Download format: HTML expected; CSV, Excel, API, JSON, and PDF depend on specific services.

Update frequency: depends on connected service.

Main identifiers: package name, institution, procurement system link, supplier/provider references where exposed, service-specific IDs.

Relevant columns: varies by service; potentially package name, institution, method, status, source service, URL.

Typical limitations: may act as portal/search/navigation rather than normalized lifecycle data warehouse.

Potential legal/licensing concerns: use public information only and follow official access rules.

How it relates to SiRUP: potential discovery layer linking planning and execution systems.

Priority for NovaNusa integration: Phase 2.

### e-Katalog

Official name: e-Katalog LKPP / Katalog Elektronik.

Official website: `https://e-katalog.lkpp.go.id/`

Managing institution: LKPP.

Purpose: publishes catalog products, suppliers, prices, classifications, and product references for catalog-based procurement.

Public availability: public product and supplier browsing is available; bulk/API access should be verified.

Download format: HTML common; CSV/Excel/API/JSON depends on official features or permitted access; PDF may exist for policy/product documents.

Update frequency: product, supplier, and price data can change frequently.

Main identifiers: product ID, catalog ID, supplier/provider ID, product category, brand, product name, price, region, supplier name.

Relevant columns: product name, product ID, category, supplier, price, unit, TKDN/PDN indicators if available, catalog type, active status, product URL.

Typical limitations: product availability does not prove a specific purchase occurred; transaction evidence is needed.

Potential legal/licensing concerns: respect LKPP terms and access limits; avoid unauthorized scraping.

How it relates to SiRUP: supports product/supplier mapping for planned e-purchasing/katalog packages, but is not transaction evidence by itself.

Priority for NovaNusa integration: Phase 2 for product intelligence; Phase 1 only where transaction evidence is public.

### e-Purchasing

Official name: e-Purchasing LKPP / purchasing through Katalog Elektronik.

Official website: generally accessed through the LKPP e-Katalog/e-Purchasing ecosystem, including `https://e-katalog.lkpp.go.id/` and related official interfaces.

Managing institution: LKPP, with buyer institutions executing purchases.

Purpose: records purchasing processes conducted through electronic catalog mechanisms.

Public availability: transaction-level public visibility may be limited or vary by interface; verify before integration.

Download format: HTML where public; CSV/Excel/API/JSON availability is uncertain unless official export/API exists.

Update frequency: frequent for active purchases.

Main identifiers: purchasing package/order ID where public, product ID, supplier, buyer institution, contract/order value, date, status.

Relevant columns: buyer, supplier, product, order/package reference, status, value, quantity, purchase date, source URL.

Typical limitations: public access to transaction detail may be incomplete; catalog product data must not be treated as purchase evidence.

Potential legal/licensing concerns: use only public transaction data; do not access private dashboards without permission.

How it relates to SiRUP: downstream evidence for packages using e-purchasing/katalog.

Priority for NovaNusa integration: Phase 1 if transaction evidence is public; otherwise Phase 2.

### SIKaP

Official name: Sistem Informasi Kinerja Penyedia.

Official website: referenced within the LKPP procurement ecosystem; current endpoint and public access should be verified from official LKPP/INAPROC sources.

Managing institution: LKPP.

Purpose: maintains provider/supplier capability and performance information.

Public availability: uncertain for broad public data use; some data may require authenticated access.

Download format: CSV/Excel/API/JSON availability uncertain; public HTML lookup should be verified.

Update frequency: changes as suppliers update profiles and performance records change.

Main identifiers: supplier/provider ID, company name, NPWP/NIB where public, classifications, qualifications, performance references.

Relevant columns: supplier identity, qualification, business classification, experience, performance, blacklist/performance indicators where legally public.

Typical limitations: may not be fully public; not direct package lifecycle evidence unless linked to winner/contract records.

Potential legal/licensing concerns: provider data may be sensitive or restricted; do not bypass authentication.

How it relates to SiRUP: useful after winner/supplier evidence exists.

Priority for NovaNusa integration: Phase 3 unless clear public access exists.

### LKPP Open Data

Official name: LKPP Open Data / Open Data Pengadaan, if available under the current LKPP public data ecosystem.

Official website: current official endpoint and dataset catalog should be verified before integration.

Managing institution: LKPP.

Purpose: provides machine-readable procurement datasets or statistics where published.

Public availability: uncertain by dataset; some datasets may be public, summarized, discontinued, or restructured.

Download format: potentially CSV, Excel, JSON, API, or HTML dashboard.

Update frequency: dataset-specific; daily, monthly, quarterly, or historical snapshots.

Main identifiers: may include RUP ID, tender ID, KLDI, supplier, method, budget, year, status.

Relevant columns: dataset-specific; inventory every downloaded file with schema, date, source URL, license, and refresh cadence.

Typical limitations: coverage, freshness, and definitions vary.

Potential legal/licensing concerns: follow dataset license and attribution requirements.

How it relates to SiRUP: may provide bulk bridge data if official identifiers exist.

Priority for NovaNusa integration: Phase 2, or Phase 1 if stable bulk lifecycle data exists.

### PPID Procurement Publications

Official name: Pejabat Pengelola Informasi dan Dokumentasi procurement publications.

Official website: each public body has its own PPID site or PPID section.

Managing institution: relevant ministry, agency, province, city/regency, hospital, university, or public institution.

Purpose: publishes legally required public information, potentially including plans, results, contracts, realization, and reports.

Public availability: public but fragmented; some records may require formal information requests.

Download format: PDF, HTML, Excel, CSV, Word documents, scanned documents.

Update frequency: varies; monthly, quarterly, annual, or ad hoc.

Main identifiers: package name, contract number, supplier, work unit, budget account, fiscal year, method, document title, publication date.

Relevant columns: package, value, supplier, contract date, status, unit, source URL; for PDFs, page and excerpt.

Typical limitations: unstructured PDFs, scans, inconsistent names, incomplete coverage, variable freshness.

Potential legal/licensing concerns: public information may require attribution; avoid restricted documents.

How it relates to SiRUP: downstream evidence for contract, delivery, payment, or completion.

Priority for NovaNusa integration: Phase 3 broadly; Phase 1 manual evidence for high-value packages.

### Tender Winner Announcements

Official name: Tender winner / pemenang announcements in SPSE/LPSE or agency publications.

Official website: SPSE/LPSE package pages and official agency/PPID procurement announcement pages.

Managing institution: procurement working group, UKPBJ/ULP, LPSE operator, buyer institution.

Purpose: identifies selected supplier and award value.

Public availability: usually public in SPSE/LPSE for tenders, but visibility varies by package type and system version.

Download format: HTML, PDF, CSV/Excel if manually exported.

Update frequency: event-driven when procurement reaches award stage.

Main identifiers: tender ID, package name, supplier, award value, RUP ID if linked, LPSE URL, winner date.

Relevant columns: winner name, bid value, corrected bid, ranking, package ID, tender ID, agency, work unit, announcement date.

Typical limitations: supplier identifiers may be partially hidden; winner existence does not always mean contract signed.

Potential legal/licensing concerns: use public data as published; avoid collecting private supplier account data.

How it relates to SiRUP: confirms movement beyond planning into award result.

Priority for NovaNusa integration: Phase 1.

### Contract Announcements

Official name: Contract announcements, pemenang berkontrak records, contract summaries, or procurement realization publications.

Official website: SPSE/LPSE where contract status is published, buyer institution websites, PPID portals, procurement bureau pages.

Managing institution: buyer institution and procurement/contracting officers.

Purpose: shows award progressed into contract.

Public availability: partially public; coverage varies by institution and system.

Download format: HTML, PDF, Excel/CSV if manually exported.

Update frequency: event-driven; may appear after signing or in periodic reports.

Main identifiers: contract number, tender ID, package ID, package name, supplier, contract value, contract date, work unit.

Relevant columns: contract number, contract date, supplier, value, package, tender ID, fiscal year, completion date if available.

Typical limitations: contract number may not be public; documents may be PDFs/scans; contract evidence may be separate from SPSE pages.

Potential legal/licensing concerns: use public documents only; do not store non-public attachments without permission.

How it relates to SiRUP: strong evidence that a planned package became a legal procurement commitment.

Priority for NovaNusa integration: Phase 1 for high-value packages; Phase 2/3 for broad coverage.

### Regional Procurement Portals

Official name: regional procurement bureau, UKPBJ, BLP, LPSE, and open data portals at provincial/city/regency level.

Official website: varies by region and institution.

Managing institution: provincial, city, regency, or regional procurement offices.

Purpose: publishes local procurement notices, tender information, procurement reports, contract summaries, and sometimes dashboards.

Public availability: varies widely.

Download format: HTML, PDF, Excel, CSV, open data API in some regions.

Update frequency: active tenders may update frequently; reports may update monthly/quarterly/yearly.

Main identifiers: package name, institution, work unit, tender ID, contract number, supplier, fiscal year, budget.

Relevant columns: package, method, stage, winner, contract value, date, agency, source URL.

Typical limitations: fragmentation, inconsistent schema, changing URLs, scanned PDFs, inconsistent update cadence.

Potential legal/licensing concerns: respect local site terms and robots.txt; do not bypass authentication.

How it relates to SiRUP: useful where central aggregation is incomplete or regional portals publish richer evidence.

Priority for NovaNusa integration: Phase 3 broadly; Phase 1 manual collection for priority regions/accounts.

### National Procurement Statistics

Official name: LKPP procurement statistics, INAPROC statistics, or other official national procurement dashboards/publications.

Official website: LKPP/INAPROC official portals and LKPP publication pages.

Managing institution: LKPP.

Purpose: aggregate procurement metrics by year, method, institution, region, supplier category, or policy dimension.

Public availability: generally public for dashboards/reports, but granular download varies.

Download format: HTML dashboards, PDF reports, Excel/CSV/JSON/API if provided.

Update frequency: monthly, quarterly, annual, or dashboard-driven.

Main identifiers: year, institution, method, category, region; package-level IDs may not be available.

Relevant columns: total packages, total value, method distribution, institution/region/category breakdowns, award/completion metrics if published.

Typical limitations: aggregate, not package-level; cannot usually prove lifecycle status for a specific SiRUP row.

Potential legal/licensing concerns: follow publication license and attribution.

How it relates to SiRUP: useful for benchmarking and validation, not primary lifecycle evidence.

Priority for NovaNusa integration: Phase 3.

### Blacklist / Sanctions Provider Data

Official name: Daftar Hitam Nasional or official provider sanction/blacklist data, if published by LKPP or authorized bodies.

Official website: LKPP official procurement/provider information channels; current endpoint should be verified.

Managing institution: LKPP and relevant authorized government bodies.

Purpose: identifies sanctioned providers that may affect procurement risk analysis.

Public availability: some blacklist information is public, but current access format and scope should be verified.

Download format: HTML, PDF, Excel/CSV/API if officially provided.

Update frequency: event-driven.

Main identifiers: supplier/provider name, NPWP/NIB where public, sanction period, issuing institution, reason/category.

Relevant columns: provider name, sanction status, period, issuing institution, legal basis, source URL.

Typical limitations: name matching can be difficult; supplier risk data is not direct package lifecycle evidence.

Potential legal/licensing concerns: use carefully and cite source; avoid defamatory interpretation beyond published facts.

How it relates to SiRUP: useful after winner/supplier is known.

Priority for NovaNusa integration: Phase 3.

### Audit and Oversight Publications

Official name: BPK audit reports, BPKP or inspectorate summaries, procurement audit findings, and official oversight reports.

Official website: BPK, BPKP, inspectorate, and agency PPID/publication portals.

Managing institution: audit and oversight institutions.

Purpose: post-facto evidence about procurement realization, irregularities, delivery issues, or contract performance.

Public availability: some reports are public; detailed attachments may not be public.

Download format: PDF, HTML, rarely Excel/CSV.

Update frequency: periodic or event-driven; often lagging.

Main identifiers: institution, fiscal year, package name, contract number, supplier, finding number.

Relevant columns: finding title, package, supplier, value, issue, recommendation, agency response.

Typical limitations: not comprehensive for all packages; unstructured and delayed.

Potential legal/licensing concerns: use only public reports and avoid overclaiming beyond audit text.

How it relates to SiRUP: delivery/payment/completion/risk evidence after procurement execution.

Priority for NovaNusa integration: Phase 3.

### Other Official Procurement-Related Sources

Other potentially useful official sources include agency procurement bureau websites, APBD/APBN realization portals, official hospital or university procurement pages, and official open data portals operated by central or regional governments.

These sources should be integrated only after verifying public availability, licensing, identifiers, and whether they contain package-level evidence. When uncertain, NovaNusa should label the source as "candidate source - verification needed" rather than treating it as authoritative.

## 4. Data Relationship Map

The central relationship problem is linking a planned SiRUP package to downstream execution records.

Key identifiers:

- RUP ID: strongest planning identifier. Use exact match if downstream evidence includes it.
- Package ID: may mean SiRUP reference ID, SPSE tender ID, LPSE package ID, e-purchasing order/package ID, or another local system ID. Always store identifier type.
- Institution: KLDI or buyer institution name. Normalize but preserve raw text.
- Work Unit: satker/satuan kerja. Often more precise than KLDI.
- KLDI: parent institution. Useful context, but too broad for exact package matching by itself.
- Budget: SiRUP pagu, SPSE HPS, bid value, award value, or contract value. Supporting evidence only.
- Procurement Method: planned method in SiRUP versus actual method downstream. Method may change.
- Year: fiscal year and process year. Use to narrow candidates.
- Package Name: useful but unstable. Normalize punctuation, casing, abbreviations, and boilerplate.
- Supplier/Winner: appears after award. Links award and contract evidence to a package.
- Contract Number: strongest contract-stage identifier when public.

Recommended canonical entities:

- `procurement_plan`: SiRUP planning row.
- `procurement_process`: SPSE/LPSE tender or non-tender process.
- `procurement_award`: winner/pemenang record.
- `procurement_contract`: contract/berkontrak record.
- `procurement_purchase`: e-purchasing/katalog transaction evidence.
- `procurement_delivery`: delivery/BAST or completion evidence.
- `supplier`: provider/winner/vendor.
- `institution`: KLDI and work unit hierarchy.
- `evidence_source`: raw source file, URL, download timestamp, source type, and license/access notes.

## 5. Matching Strategy

NovaNusa should use factual matching only. It should not create a lifecycle scoring system that implies status without evidence.

Matching hierarchy:

1. Exact ID

Use exact RUP ID, tender ID, package ID, e-purchasing order/package ID, or source-specific ID when present. Preserve identifier type.

2. Package ID

If RUP ID is absent but another package ID exists, match only when identifier type is known or strongly inferred.

3. Contract number

For contract-stage evidence, contract number is strong evidence when linked to package name, institution, supplier, or value.

4. Institution

Use KLDI plus work unit/satker. Institution alone is not enough for lifecycle status because many packages share the same institution.

5. Normalized package name

Normalize package names by lowercasing, removing punctuation, collapsing whitespace, and optionally removing procurement boilerplate such as "belanja modal," "pengadaan," or fiscal-year suffixes. Package-name match must be supported by institution, year, budget, or ID.

6. Budget

Use budget similarity as supporting evidence. SiRUP pagu, HPS, bid value, and contract value may differ.

7. Year

Use fiscal year/process year to narrow matches. Year supports confidence but should not be sole evidence.

8. Manual review

When multiple candidate matches are close, assign `NEEDS_MANUAL_CHECK`. Manual reviewers should inspect source URLs/files and record the reason for final status.

Evidence requirements:

- Every non-planning status must have `source_type`.
- Every non-planning status must have `source_url` or `source_file/reference` where available.
- Every non-planning status must include matched text or extracted source row.
- Every non-planning status must explain match basis.
- `PLANNING_ONLY_SIRUP` must mean only "no downstream public match found in available evidence."

## 6. Data Freshness

Datasets that may change daily or more often:

- SPSE Nasional active tender/non-tender search and package pages.
- LPSE active process pages.
- e-purchasing transaction/process evidence where public.
- e-Katalog product and price data.
- Winner and contract status for active processes.

Datasets that change during planning/revision cycles:

- SiRUP planning rows.
- Budget revisions, package revisions, work unit changes, planned method changes, planned month changes.

Historical or slower-changing datasets:

- Completed tender archives.
- PPID procurement reports.
- Contract publication PDFs.
- Audit reports.
- National procurement statistics.
- Provider blacklist/sanction archives.

Recommended synchronization:

- SiRUP: daily during active planning/procurement season, weekly for historical years.
- SPSE/LPSE active packages: daily for priority packages, weekly for broad monitoring if permitted.
- Winner/contract evidence: daily for active packages near evaluation/award stages.
- e-Katalog products: weekly/monthly depending on use case.
- e-purchasing transaction evidence: daily if public and permitted.
- PPID and audit documents: monthly/quarterly/manual collection.
- Statistics: monthly/quarterly/annual.

## 7. Legal and Ethical Considerations

Public procurement transparency exists to support accountability, fair competition, and informed public oversight. NovaNusa should preserve those goals.

Principles:

- Use only publicly available information unless explicit permission exists.
- Respect robots.txt and site terms where applicable.
- Do not bypass authentication, CAPTCHA, rate limits, or access controls.
- Do not use private buyer/supplier dashboards without permission.
- Prefer official APIs, open data downloads, or manual exports over scraping.
- Store source URL, download date, and license/access notes for every evidence file.
- Do not fabricate missing status, contacts, contract numbers, winners, or dates.
- Do not infer "still open" from SiRUP alone.
- Treat supplier and contact data carefully; do not use procurement transparency data for spam.
- When a source is uncertain, label it as uncertain rather than guessing.

## 8. Recommended NovaNusa Data Lake

NovaNusa should organize procurement data as an evidence-first data lake, not as a single flattened leads table.

### Raw Source Zone

Stores exact downloaded source files:

- SiRUP DuckDB/CSV/XLSX snapshots.
- SPSE Nasional exports or saved pages.
- LPSE exports or saved pages.
- e-purchasing/katalog evidence files.
- Winner announcements.
- Contract announcements.
- PPID PDFs/HTML/XLSX.
- Regional procurement portal exports.
- Audit/statistics files.

Every raw file should have metadata: source name, official URL, download date, collector, source type, license/access note, file hash, and collection method.

### Parsed Evidence Zone

Stores extracted rows with source traceability:

- `evidence_source_id`
- `source_type`
- `source_url`
- `source_file`
- `matched_text`
- raw identifiers
- parsed identifiers
- parsed package names
- parsed institution names
- parsed budgets
- parsed dates
- parsed statuses

### Canonical Entity Zone

Stores normalized entities:

- institutions
- work units
- procurement plans
- procurement processes
- awards
- contracts
- purchases
- suppliers
- products/categories

### Relationship Zone

Stores factual links:

- plan-to-process match
- process-to-award match
- award-to-contract match
- plan-to-e-purchasing match
- contract-to-delivery evidence
- contract-to-payment evidence where public

Each relationship must store match basis, confidence explanation, reviewer status, and source evidence.

### Analytics / Workspace Zone

Supports NovaNusa workflows:

- entity workspace
- opportunity workspace
- manual review queue
- procurement lifecycle timeline
- supplier/institution intelligence
- evidence audit trail

## 9. Integration Roadmap

### Phase 1: Highest Value

1. SiRUP

Reason: planning anchor and universe of packages, institutions, budgets, methods, and planned timing.

2. SPSE Nasional and LPSE package evidence

Reason: strongest public downstream source for moving from planning to announcement, tender/non-tender, winner, cancelled/failed, and sometimes contract status.

3. Winner announcements

Reason: high business value and direct evidence that procurement moved beyond planning.

4. Contract/berkontrak evidence where public

Reason: strongest signal that an award became an actual procurement commitment.

5. Manual evidence collection folders

Reason: validates matching logic before broad automation and supports high-value packages such as May/June 2026 healthcare equipment.

### Phase 2: Expansion

1. e-Purchasing transaction evidence if publicly available

Reason: critical for katalog/e-purchasing packages, but transaction-level public access must be verified.

2. e-Katalog product/supplier data

Reason: useful for product/principal matching and supplier intelligence, but product data alone does not prove a purchase.

3. LKPP Open Data if available and stable

Reason: could provide bulk structured data and reduce manual collection if official datasets exist.

4. INAPROC discovery/search metadata

Reason: useful as national discovery layer once direct SiRUP/SPSE/LPSE ingestion is stable.

5. Regional procurement portals for priority regions

Reason: adds coverage where central aggregation is incomplete or where regional portals publish richer documents.

### Phase 3: Advanced Evidence and Governance

1. PPID procurement publications

Reason: useful for contract, delivery, payment, and completion evidence, but fragmented and often unstructured.

2. Audit and oversight publications

Reason: useful for risk and post-completion intelligence, but lagging and not comprehensive.

3. SIKaP/provider performance data if publicly usable

Reason: potentially valuable for supplier intelligence after winner/contract matching, but public access and legal use must be verified.

4. National procurement statistics

Reason: useful for benchmarking and macro analytics, but not package-level lifecycle proof.

5. Payment and delivery evidence where legally public

Reason: high value for lifecycle completion, but often not consistently public at package level.

Recommended starting point:

NovaNusa should first stabilize the factual chain:

SiRUP plan -> SPSE/LPSE process -> winner -> contract -> manual review notes.

Only after this chain is reliable should NovaNusa invest heavily in product catalog enrichment, regional portal expansion, PPID document extraction, and supplier risk analytics.
