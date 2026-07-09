import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { formatIdr } from "@/lib/institution-data";
import { getProductMatchesWithDataSet } from "@/lib/product-intelligence";
import ProductsClient from "./products-client";

export const dynamic = "force-dynamic";

export default function ProductsPage() {
  const { matches, dataSet } = getProductMatchesWithDataSet();
  const totalCategories = new Set(matches.map((match) => match.product.productCategory)).size;
  const matchedInstitutionIds = new Set(matches.flatMap((match) => match.matchedInstitutions.map((institution) => institution.institution_id)));
  const matchedPaguByInstitution = new Map<string, number>();

  for (const match of matches) {
    for (const institution of match.matchedInstitutions) {
      matchedPaguByInstitution.set(institution.institution_id, institution.total_pagu);
    }
  }

  const rows = matches.map((match) => ({
    product: match.product,
    needCategories: match.needCategories,
    matchedInstitutionCount: match.matchedInstitutions.length,
    matchedPagu: match.matchedPagu,
  }));

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Card className="p-6 md:p-7">
        <PageHeader
          eyebrow="Product Intelligence"
          title="Products"
          description="Map provider and principal product coverage to existing SiRUP institution needs using planning evidence only."
          actions={<div className="flex flex-wrap gap-2"><Badge tone="info">SiRUP Planning Evidence Only</Badge><Badge tone="warning">No tender status inferred</Badge></div>}
        />
        <div className="mt-4 flex flex-col gap-3 text-sm leading-6 text-slate-600 lg:flex-row lg:items-center lg:justify-between">
          <p>{dataSet.usingSeedFallback ? "No synced product store found. Showing manual seed data pending INAPROC verification." : "Showing synced product store data pending INAPROC verification."}</p>
          <div className="flex flex-wrap gap-2">
            <Badge tone={dataSet.usingSeedFallback ? "warning" : "info"}>{dataSet.source}</Badge>
            <Badge tone="warning">{dataSet.evidence_status}</Badge>
          </div>
        </div>
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Product intelligence KPIs">
        <KPI label="Total Products" value={matches.length.toLocaleString("id-ID")} detail={dataSet.usingSeedFallback ? "Manual seed records available for product-to-need mapping." : "Synced product records available for product-to-need mapping."} badge="Products" />
        <KPI label="Total Categories" value={totalCategories.toLocaleString("id-ID")} detail="Product categories mapped to dashboard need categories." badge="Categories" />
        <KPI label="Total Matched Institutions" value={matchedInstitutionIds.size.toLocaleString("id-ID")} detail="Unique institutions with matching SiRUP planning evidence." badge="Institutions" href="/institutions" />
        <KPI label="Total Matched Pagu" value={formatIdr(Array.from(matchedPaguByInstitution.values()).reduce((sum, value) => sum + value, 0))} detail="Unique institution pagu represented by product matches." badge="Pagu" href="/outreach/prospect-queue" />
      </section>

      <ProductsClient rows={rows} dataSource={dataSet} />
    </div>
  );
}
