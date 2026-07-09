import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { loadProspects } from "@/lib/institution-data";

export default function BuktiPage() {
  const institutions = loadProspects();
  const sirupPlanningOnly = institutions.filter((item) => item.evidence_status === "SIRUP_PLANNING_ONLY").length;
  const spseNotChecked = institutions.filter((item) => item.spse_status === "SPSE_NOT_CHECKED_NATIONALLY").length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Bukti"
            title="Bukti"
            description="Bukti perencanaan SiRUP and SPSE national check status for institution-level operational review."
            actions={
              <div className="flex flex-wrap gap-2">
                <Badge tone="info">SIRUP_PLANNING_ONLY</Badge>
                <Badge>SPSE_NOT_CHECKED_NATIONALLY</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 md:grid-cols-2" aria-label="Bukti KPIs">
          <KPI label="SiRUP Bukti" value={sirupPlanningOnly.toLocaleString("id-ID")} detail="Data yang ditandai sebagai bukti perencanaan SiRUP saja." badge="SiRUP" href="/evidence" />
          <KPI label="Status SPSE" value={spseNotChecked.toLocaleString("id-ID")} detail="Data yang belum dicek secara nasional di SPSE." badge="SPSE" href="/evidence" />
        </section>

        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Bukti rule</p>
          <p className="mt-3 text-sm leading-6 text-slate-600">NovaNusa menggunakan status bukti dataset sebagai bukti perencanaan saja. Status SPSE tetap belum dicek secara nasional, dan status tender tidak disimpulkan.</p>
        </Card>
    </div>
  );
}
