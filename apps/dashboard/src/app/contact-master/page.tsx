import Link from "next/link";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { loadProspects } from "@/lib/institution-data";

export default function KontakMasterPage() {
  const institutions = loadProspects();
  const contactFound = institutions.filter((item) => item.contact_status === "CONTACT_FOUND").length;
  const needsReview = institutions.filter((item) => item.contact_status === "CONTACT_NEEDS_REVIEW").length;
  const missing = institutions.filter((item) => item.contact_status === "Kontak Belum Ada").length;
  const reviewRows = institutions.filter((item) => item.contact_status !== "Kontak Belum Ada").slice(0, 12);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Kontak Master"
            title="Kontak Master"
            description="Tinjau data kontak institusi dan bukti sumber sebelum menyusun outreach."
            actions={<Link href="/outreach/prospect-queue" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Buka Prospek</Link>}
          />
        </Card>

        <section className="grid gap-4 sm:grid-cols-3" aria-label="Kontak master KPIs">
          <KPI label="Kontak ditemukan" value={contactFound.toLocaleString("id-ID")} detail="Email and source data are available for review." badge="Found" href="/contact-master" />
          <KPI label="Perlu ditinjau" value={needsReview.toLocaleString("id-ID")} detail="Kontak exists, but source evidence needs checking." badge="Review" href="/contact-master" />
          <KPI label="Belum ada" value={missing.toLocaleString("id-ID")} detail="Belum ada kontak yang terhubung." badge="Belum ada" href="/contact-master" />
        </section>

        <Card className="overflow-hidden">
          <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Antrean tinjauan</p>
            <h2 className="mt-1 text-base font-semibold text-slate-950">Data kontak tersedia</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
                <tr>
                  <th className="border-b border-slate-200 px-5 py-3">Institusi</th>
                  <th className="border-b border-slate-200 px-5 py-3">Kontak status</th>
                  <th className="border-b border-slate-200 px-5 py-3">Email</th>
                  <th className="border-b border-slate-200 px-5 py-3">URL sumber</th>
                  <th className="border-b border-slate-200 px-5 py-3">Workspace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200/80 bg-white">
                {reviewRows.map((item) => (
                  <tr key={item.institution_id} className="align-top transition-colors hover:bg-slate-50/80">
                    <td className="max-w-[320px] px-5 py-4 font-medium text-slate-950">{item.institution_display_name}</td>
                    <td className="px-5 py-4"><Badge>{item.contact_status}</Badge></td>
                    <td className="max-w-[240px] px-5 py-4 text-xs leading-5 text-slate-600">{item.contact_email}</td>
                    <td className="max-w-[280px] px-5 py-4 text-xs leading-5 text-slate-600">{item.contact_source_url}</td>
                    <td className="px-5 py-4"><Link href={`/institutions/${item.institution_id}`} className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Buka</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
    </div>
  );
}
