import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { loadProspects } from "@/lib/institution-data";

export default function EvidencePage() {
  const institutions = loadProspects();
  const sirupPlanningOnly = institutions.filter((item) => item.evidence_status === "SIRUP_PLANNING_ONLY").length;
  const spseNotChecked = institutions.filter((item) => item.spse_status === "SPSE_NOT_CHECKED_NATIONALLY").length;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Evidence"
            title="Evidence"
            description="SiRUP planning evidence and SPSE national check status for institution-level operational review."
            actions={
              <div className="flex flex-wrap gap-2">
                <Badge tone="info">SIRUP_PLANNING_ONLY</Badge>
                <Badge>SPSE_NOT_CHECKED_NATIONALLY</Badge>
              </div>
            }
          />
        </Card>

        <section className="grid gap-4 md:grid-cols-2" aria-label="Evidence KPIs">
          <KPI label="SiRUP Evidence" value={sirupPlanningOnly.toLocaleString("id-ID")} detail="Records marked as SiRUP planning-only evidence." badge="SiRUP" href="/evidence" />
          <KPI label="SPSE Status" value={spseNotChecked.toLocaleString("id-ID")} detail="Records not checked nationally in SPSE." badge="SPSE" href="/evidence" />
        </section>

        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Evidence rule</p>
          <p className="mt-3 text-sm leading-6 text-slate-600">NovaNusa uses the dataset evidence status as planning evidence only. SPSE status remains not checked nationally, and tender status is not inferred.</p>
        </Card>
    </div>
  );
}
