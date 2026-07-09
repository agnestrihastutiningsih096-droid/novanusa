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
          eyebrow="Intelijen Produk"
          title="Produk"
          description="Petakan cakupan produk penyedia dan principal ke kebutuhan institusi dari SiRUP dengan bukti perencanaan saja."
          actions={<div className="flex flex-wrap gap-2"><Badge tone="info">Hanya Bukti Perencanaan SiRUP</Badge><Badge tone="warning">Status tender tidak disimpulkan</Badge></div>}
        />
        <div className="mt-4 flex flex-col gap-3 text-sm leading-6 text-slate-600 lg:flex-row lg:items-center lg:justify-between">
          <p>{dataSet.usingSeedFallback ? "Store produk sinkron belum ditemukan. Menampilkan data awal manual sambil menunggu verifikasi INAPROC." : "Menampilkan data store produk sinkron sambil menunggu verifikasi INAPROC."}</p>
          <div className="flex flex-wrap gap-2">
            <Badge tone={dataSet.usingSeedFallback ? "warning" : "info"}>{dataSet.source}</Badge>
            <Badge tone="warning">{dataSet.evidence_status}</Badge>
          </div>
        </div>
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Product intelligence KPIs">
        <KPI label="Total Produk" value={matches.length.toLocaleString("id-ID")} detail={dataSet.usingSeedFallback ? "Data awal manual tersedia untuk pemetaan produk ke kebutuhan." : "Data produk sinkron tersedia untuk pemetaan produk ke kebutuhan."} badge="Products" />
        <KPI label="Total Kategori" value={totalCategories.toLocaleString("id-ID")} detail="Kategori produk dipetakan ke kategori kebutuhan dashboard." badge="Categories" />
        <KPI label="Total Institusi Cocok" value={matchedInstitutionIds.size.toLocaleString("id-ID")} detail="Institusi unik dengan bukti perencanaan SiRUP yang cocok." badge="Institutions" href="/institutions" />
        <KPI label="Total Pagu Cocok" value={formatIdr(Array.from(matchedPaguByInstitution.values()).reduce((sum, value) => sum + value, 0))} detail="Pagu institusi unik yang terwakili oleh kecocokan produk." badge="Pagu" href="/outreach/prospect-queue" />
      </section>

      <ProductsClient rows={rows} dataSource={dataSet} />
    </div>
  );
}
