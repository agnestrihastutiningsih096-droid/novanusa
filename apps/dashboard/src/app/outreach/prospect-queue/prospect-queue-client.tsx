"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { formatIdr, splitExamples, splitList, type Prospect } from "@/lib/institution-utils";

type Tab = "May 2026" | "June 2026" | "May + June";
type OperationalFilter = "ALL" | "CONTACT_FOUND" | "READY_FOR_DRAFT" | "READY_TO_SEND";

type ProspectQueueClientProps = {
  prospects: Prospect[];
  csvPath: string;
};

const tabs: Tab[] = ["May 2026", "June 2026", "May + June"];
const targetLevelOptions = ["NATIONAL", "PROVINCE", "LOCAL_AGENCY", "HOSPITAL", "EDUCATION", "HEALTH_UNIT", "OTHER", "REVIEW"];
const sendReadinessOptions = ["READY_FOR_CONTACT_SEARCH", "NEEDS_REVIEW"];
const contactStatusOptions = ["CONTACT_FOUND", "CONTACT_NEEDS_REVIEW", "CONTACT_MISSING"];
const outreachStatuses = ["NOT_CONTACTED", "DRAFT_GENERATED", "DRAFT_EDITED", "APPROVED", "READY_TO_SEND", "SENT"];
const operationalFilterOptions: Array<{ label: string; value: OperationalFilter }> = [
  { label: "Semua", value: "ALL" },
  { label: "Kontak Ditemukan", value: "CONTACT_FOUND" },
  { label: "Siap Draf", value: "READY_FOR_DRAFT" },
  { label: "Siap Dikirim", value: "READY_TO_SEND" },
];

function hasContactEmail(prospect: Prospect) {
  return prospect.contact_email.trim().length > 0;
}

function contactPriority(prospect: Prospect) {
  return hasContactEmail(prospect) ? 0 : 1;
}

function buildDraft(prospect: Prospect) {
  const categories = splitList(prospect.relevant_categories).join(", ") || "kebutuhan yang tercatat dalam data perencanaan";
  const year = prospect.months_found.match(/20\d{2}/)?.[0] ?? new Date().getFullYear().toString();

  return `Yth. Bapak/Ibu,

Perkenalkan, saya tim sales dari perusahaan kami. Kami menyediakan produk dan layanan terkait ${categories} untuk mendukung kebutuhan ${categories} bagi berbagai institusi dan organisasi.

Kami menghubungi Bapak/Ibu terkait rencana pengadaan ${categories} oleh ${prospect.institution_display_name} untuk tahun ${year}, sebagaimana dipublikasikan melalui SiRUP sebagai data perencanaan pengadaan.

Terkait kebutuhan tersebut, kami dapat menyediakan informasi produk, spesifikasi teknis, katalog, maupun referensi implementasi yang relevan sebagai bahan pertimbangan.

Apabila Bapak/Ibu berkenan, apakah kami dapat mengetahui PIC yang tepat untuk kebutuhan ini, atau menjadwalkan percakapan singkat melalui telepon pada waktu yang sesuai?

Terima kasih atas waktu dan perhatian Bapak/Ibu.

Hormat kami,

tim sales
perusahaan kami`;
}

function badgeToneForTargetLevel(value: string) {
  if (value === "NATIONAL" || value === "PROVINCE") {
    return "warning";
  }
  if (value === "REVIEW") {
    return "info";
  }
  return "neutral";
}

function badgeToneForSendReadiness(value: string) {
  if (value === "READY_FOR_CONTACT_SEARCH") {
    return "success";
  }
  return "warning";
}

function badgeToneForContactStatus(value: string) {
  if (value === "CONTACT_FOUND") {
    return "success";
  }
  if (value === "CONTACT_NEEDS_REVIEW") {
    return "warning";
  }
  return "neutral";
}

export default function ProspectQueueClient({ prospects, csvPath }: ProspectQueueClientProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("May + June");
  const [query, setQuery] = useState("");
  const [category, setKategori] = useState("ALL");
  const [targetLevel, setTargetLevel] = useState("ALL");
  const [contactStatus, setContactStatus] = useState("ALL");
  const [sendReadiness, setSendReadiness] = useState("ALL");
  const [operationalFilter, setOperationalFilter] = useState<OperationalFilter>("ALL");
  const [statusByInstitution, setStatusByInstitution] = useState<Record<string, string>>({});
  const [outreachStatus, setOutreachStatus] = useState("ALL");
  const [selected, setSelected] = useState<Prospect | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [editingDraft, setEditingDraft] = useState(false);

  const categories = useMemo(() => {
    return Array.from(new Set(prospects.flatMap((prospect) => splitList(prospect.relevant_categories)))).sort();
  }, [prospects]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return prospects
      .map((prospect, index) => ({ prospect, index }))
      .filter(({ prospect }) => {
        const status = statusByInstitution[prospect.institution_name] ?? prospect.outreach_status;
        const contactFound = hasContactEmail(prospect);
        const inTab = activeTab === "May + June" || prospect.months_found.includes(activeTab);
        const searchText = `${prospect.institution_display_name} ${prospect.institution_name} ${prospect.parent_organization} ${prospect.work_unit} ${prospect.location_hint} ${prospect.province_or_region} ${prospect.relevant_categories} ${prospect.contact_email}`.toLowerCase();
        const matchesQuery = !normalizedQuery || searchText.includes(normalizedQuery);
        const matchesKategori = category === "ALL" || splitList(prospect.relevant_categories).includes(category);
        const matchesTargetLevel = targetLevel === "ALL" || prospect.target_level === targetLevel;
        const matchesContact = contactStatus === "ALL" || prospect.contact_status === contactStatus;
        const matchesSendReadiness = sendReadiness === "ALL" || prospect.send_readiness === sendReadiness;
        const matchesStatus = outreachStatus === "ALL" || status === outreachStatus;
        const readyForDraft = contactFound && ["NOT_CONTACTED", ""].includes(status);
        const matchesOperational =
          operationalFilter === "ALL" ||
          (operationalFilter === "CONTACT_FOUND" && contactFound) ||
          (operationalFilter === "READY_FOR_DRAFT" && readyForDraft) ||
          (operationalFilter === "READY_TO_SEND" && status === "READY_TO_SEND");

        return inTab && matchesQuery && matchesKategori && matchesTargetLevel && matchesContact && matchesSendReadiness && matchesStatus && matchesOperational;
      })
      .sort((left, right) => {
        const priority = contactPriority(left.prospect) - contactPriority(right.prospect);
        return priority || left.index - right.index;
      })
      .map(({ prospect }) => prospect);
  }, [activeTab, category, contactStatus, operationalFilter, outreachStatus, prospects, query, sendReadiness, statusByInstitution, targetLevel]);

  function setWorkflowStatus(prospect: Prospect, status: string) {
    setStatusByInstitution((current) => ({ ...current, [prospect.institution_name]: status }));
  }

  function generateDraft(prospect: Prospect) {
    setDrafts((current) => ({ ...current, [prospect.institution_name]: current[prospect.institution_name] ?? buildDraft(prospect) }));
    setWorkflowStatus(prospect, "DRAFT_GENERATED");
    setSelected(prospect);
    setEditingDraft(false);
  }

  function statusFor(prospect: Prospect) {
    return statusByInstitution[prospect.institution_name] ?? prospect.outreach_status;
  }

  function openInstitution(institutionId: string) {
    router.push(`/institutions/${institutionId}`);
  }

  return (
    <>
      <Card className="p-5 md:p-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2" aria-label="Month tabs">
            {tabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`h-9 rounded-md border px-3 text-sm font-medium ${
                  activeTab === tab ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="grid gap-3 lg:grid-cols-[1.4fr_1fr_1fr_1fr] xl:grid-cols-[1.2fr_0.95fr_0.95fr_0.95fr_0.95fr_0.95fr]">
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Cari institusi
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Cari nama, unit, induk, wilayah, email..."
                className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Filter operasional
              <select value={operationalFilter} onChange={(event) => setOperationalFilter(event.target.value as OperationalFilter)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
                {operationalFilterOptions.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Kategori
              <select value={category} onChange={(event) => setKategori(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
                <option value="ALL">Semua categories</option>
                {categories.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Level target
              <select value={targetLevel} onChange={(event) => setTargetLevel(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
                <option value="ALL">Semua</option>
                {targetLevelOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Status kontak
              <select value={contactStatus} onChange={(event) => setContactStatus(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
                <option value="ALL">Semua</option>
                {contactStatusOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Kesiapan kirim
              <select value={sendReadiness} onChange={(event) => setSendReadiness(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
                <option value="ALL">Semua</option>
                {sendReadinessOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400 lg:max-w-xs">
            Status outreach
            <select value={outreachStatus} onChange={(event) => setOutreachStatus(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
              <option value="ALL">Semua outreach statuses</option>
              {outreachStatuses.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
          </label>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Tabel institusi</p>
              <h2 className="mt-1 text-base font-semibold text-slate-950">{filtered.length.toLocaleString("id-ID")} institusi ditampilkan</h2>
              <p className="mt-1 text-sm text-slate-600">Antrean operasional menampilkan institusi yang sesuai dengan data email kontak di urutan awal.</p>
            </div>
            <Badge>Workflow lokal saja</Badge>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[1880px] border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              <tr>
                <th className="border-b border-slate-200 px-5 py-3">Tampilan institusi</th>
                <th className="border-b border-slate-200 px-5 py-3">Level target</th>
                <th className="border-b border-slate-200 px-5 py-3">Kesiapan kirim</th>
                <th className="border-b border-slate-200 px-5 py-3">Paket</th>
                <th className="border-b border-slate-200 px-5 py-3">Pagu</th>
                <th className="border-b border-slate-200 px-5 py-3">Organisasi induk</th>
                <th className="border-b border-slate-200 px-5 py-3">Unit kerja</th>
                <th className="border-b border-slate-200 px-5 py-3">Petunjuk wilayah</th>
                <th className="border-b border-slate-200 px-5 py-3">Bulan</th>
                <th className="border-b border-slate-200 px-5 py-3">Kategori</th>
                <th className="border-b border-slate-200 px-5 py-3">Bukti</th>
                <th className="border-b border-slate-200 px-5 py-3">SPSE</th>
                <th className="border-b border-slate-200 px-5 py-3">Status kontak</th>
                <th className="border-b border-slate-200 px-5 py-3">Email kontak</th>
                <th className="border-b border-slate-200 px-5 py-3">Situs resmi</th>
                <th className="border-b border-slate-200 px-5 py-3">URL sumber kontak</th>
                <th className="border-b border-slate-200 px-5 py-3">Outreach</th>
                <th className="border-b border-slate-200 px-5 py-3">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/80 bg-white">
              {filtered.map((prospect) => (
                <tr
                  key={prospect.institution_name}
                  role="link"
                  tabIndex={0}
                  onClick={() => openInstitution(prospect.institution_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openInstitution(prospect.institution_id);
                    }
                  }}
                  className="cursor-pointer align-top transition-colors hover:bg-slate-50/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-blue-300"
                >
                  <td className="max-w-[300px] px-5 py-4 font-medium text-slate-950">
                    <span className="text-slate-950 underline-offset-4 hover:text-blue-700 hover:underline">
                      {prospect.institution_display_name}
                    </span>
                    <div className="mt-1 text-xs text-slate-500">{prospect.institution_name}</div>
                  </td>
                  <td className="px-5 py-4"><Badge tone={badgeToneForTargetLevel(prospect.target_level)}>{prospect.target_level}</Badge></td>
                  <td className="px-5 py-4"><Badge tone={badgeToneForSendReadiness(prospect.send_readiness)}>{prospect.send_readiness}</Badge></td>
                  <td className="px-5 py-4 text-slate-700">{prospect.total_relevant_packages.toLocaleString("id-ID")}</td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-700">{formatIdr(prospect.total_pagu)}</td>
                  <td className="max-w-[220px] px-5 py-4 text-sm text-slate-600">{prospect.parent_organization}</td>
                  <td className="max-w-[220px] px-5 py-4 text-sm text-slate-600">{prospect.work_unit}</td>
                  <td className="max-w-[180px] px-5 py-4 text-sm text-slate-600">{prospect.province_or_region}</td>
                  <td className="px-5 py-4 text-slate-600">{prospect.months_found}</td>
                  <td className="max-w-[260px] px-5 py-4 text-slate-600">{prospect.relevant_categories}</td>
                  <td className="px-5 py-4"><Badge tone="info">{prospect.evidence_status}</Badge></td>
                  <td className="px-5 py-4"><Badge>{prospect.spse_status}</Badge></td>
                  <td className="px-5 py-4"><Badge tone={badgeToneForContactStatus(prospect.contact_status)}>{prospect.contact_status}</Badge></td>
                  <td className="max-w-[220px] px-5 py-4 text-xs leading-5 text-slate-600">{prospect.contact_email || "CONTACT_MISSING"}</td>
                  <td className="max-w-[220px] px-5 py-4 text-xs leading-5 text-slate-600">{prospect.official_website || ""}</td>
                  <td className="max-w-[240px] px-5 py-4 text-xs leading-5 text-slate-600">{prospect.contact_source_url || ""}</td>
                  <td className="px-5 py-4"><Badge>{statusFor(prospect)}</Badge></td>
                  <td className="px-5 py-4">
                    <div className="flex w-[440px] flex-wrap gap-2">
                      <Link href={`/institutions/${prospect.institution_id}`} onClick={(event) => event.stopPropagation()} className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Buka Workspace</Link>
                      <button type="button" onClick={(event) => { event.stopPropagation(); setSelected(prospect); setEditingDraft(false); }} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Preview Bukti</button>
                      <button type="button" onClick={(event) => { event.stopPropagation(); generateDraft(prospect); }} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Buat Draf</button>
                      <button type="button" onClick={(event) => { event.stopPropagation(); generateDraft(prospect); setWorkflowStatus(prospect, "DRAFT_EDITED"); setEditingDraft(true); }} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Edit Draf</button>
                      <button type="button" onClick={(event) => { event.stopPropagation(); setWorkflowStatus(prospect, "APPROVED"); }} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Setujui</button>
                      <button type="button" onClick={(event) => { event.stopPropagation(); setWorkflowStatus(prospect, "READY_TO_SEND"); }} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Siap Dikirim</button>
                      <button type="button" onClick={(event) => { event.stopPropagation(); setWorkflowStatus(prospect, "SENT"); }} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Tandai Terkirim</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selected ? (
        <Card className="p-5 md:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Bukti preview</p>
              <h2 className="mt-2 text-base font-semibold text-slate-950">{selected.institution_display_name}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">Ekspor sumber: {csvPath}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge tone={badgeToneForTargetLevel(selected.target_level)}>{selected.target_level}</Badge>
              <Badge tone={badgeToneForSendReadiness(selected.send_readiness)}>{selected.send_readiness}</Badge>
              <Badge tone={badgeToneForContactStatus(selected.contact_status)}>{selected.contact_status}</Badge>
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1fr]">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Bukti details</p>
              <div className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                <p>Email kontak: {selected.contact_email || "CONTACT_MISSING"}</p>
                <p>Situs resmi: {selected.official_website || ""}</p>
                <p>URL sumber kontak: {selected.contact_source_url || ""}</p>
                <p>Kategori relevan: {selected.relevant_categories}</p>
                <p>Organisasi induk: {selected.parent_organization}</p>
                <p>Unit kerja: {selected.work_unit}</p>
                <p>Petunjuk wilayah: {selected.province_or_region}</p>
              </div>
              <div className="mt-4">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Contoh nama paket</p>
                <ul className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
                  {splitExamples(selected.example_package_names).map((example) => (
                    <li key={example}>{example}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="rounded-md border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Draf email</p>
                <button type="button" onClick={() => generateDraft(selected)} className="h-8 rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Buat Draf</button>
              </div>
              {drafts[selected.institution_name] ? (
                editingDraft ? (
                  <textarea
                    value={drafts[selected.institution_name]}
                    onChange={(event) => setDrafts((current) => ({ ...current, [selected.institution_name]: event.target.value }))}
                    className="mt-3 min-h-64 w-full rounded-md border border-slate-200 p-3 text-sm leading-6 text-slate-700 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
                  />
                ) : (
                  <pre className="mt-3 whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm leading-6 text-slate-700">{drafts[selected.institution_name]}</pre>
                )
              ) : (
                <p className="mt-3 text-sm leading-6 text-slate-600">Draf belum dibuat untuk institusi ini.</p>
              )}
            </div>
          </div>
        </Card>
      ) : null}
    </>
  );
}
