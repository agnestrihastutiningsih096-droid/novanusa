import Link from "next/link";
import { notFound } from "next/navigation";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import KPI from "@/components/common/KPI";
import PageHeader from "@/components/common/PageHeader";
import { formatIdr } from "@/lib/institution-data";
import { findProductById, matchProductToProspects, productRecords } from "@/lib/product-intelligence";

type ProductDetailPageProps = { params: Promise<{ id: string }> };

export function generateStaticParams() {
  return productRecords.map((product) => ({ id: product.id }));
}

export default async function ProductDetailPage({ params }: ProductDetailPageProps) {
  const { id } = await params;
  const product = findProductById(id);
  if (!product) notFound();

  const match = matchProductToProspects(product);
  const examplePackages = match.examplePackages.slice(0, 12);
  const institutions = match.matchedInstitutions.slice(0, 25);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
      <Card className="p-6 md:p-7">
        <PageHeader
          eyebrow="Product Detail"
          title={product.productName}
          description="Review product profile, pending product evidence, and SiRUP institution need matches. This page is evidence matching only."
          actions={<div className="flex flex-wrap gap-2"><Badge tone="info">SiRUP Planning Evidence Only</Badge><Badge tone="warning">Product data pending INAPROC verification</Badge><Badge>No tender status inferred</Badge></div>}
        />
      </Card>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Product match KPIs">
        <KPI label="Matched institutions" value={match.matchedInstitutions.length.toLocaleString("id-ID")} detail="Institution records matched by need category or package keywords." badge="Evidence" href="/institutions" />
        <KPI label="Matched pagu" value={formatIdr(match.matchedPagu)} detail="Total pagu across matched institution planning rows." badge="Pagu" href="/outreach/prospect-queue" />
        <KPI label="Need categories" value={match.needCategories.length.toLocaleString("id-ID")} detail={match.needCategories.join(", ")} badge="Needs" />
        <KPI label="Evidence source" value={product.evidenceSource} detail="Seed status for the product record." badge="Product" />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_1fr]" aria-label="Product profile and evidence status">
        <Card className="p-5 md:p-6">
          <div className="flex items-start justify-between gap-3">
            <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Product profile</p><h2 className="mt-2 text-base font-semibold text-slate-950">{product.productName}</h2></div>
            <Badge>{product.productCategory}</Badge>
          </div>
          <dl className="mt-4 grid gap-3 text-sm leading-6 text-slate-700 sm:grid-cols-2">
            <DetailItem label="Provider" value={`${product.providerName} (${product.providerType})`} />
            <DetailItem label="Principal" value={product.principalName} />
            <DetailItem label="Brand" value={product.brand} />
            <DetailItem label="Subcategory" value={product.productSubcategory} />
            <DetailItem label="TKDN" value={product.tkdn} />
            <DetailItem label="Price info" value={product.priceInfo} />
          </dl>
        </Card>

        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Evidence status</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Verification boundaries</h2>
          <div className="mt-4 flex flex-wrap gap-2"><Badge tone="warning">{product.status}</Badge><Badge tone="info">{product.evidenceSource}</Badge><Badge>No tender status inferred</Badge></div>
          <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
            <p>Product data pending INAPROC verification. This record is a manual seed for product coverage mapping, not a verified catalog listing.</p>
            <p>Matched SiRUP need categories are derived from existing dashboard planning categories and package examples.</p>
            <p>Source URL: {product.sourceUrl || "Not available in manual seed"}</p>
          </div>
        </Card>
      </section>

      <Card className="p-5 md:p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Category and keywords</p><h2 className="mt-2 text-base font-semibold text-slate-950">Matched SiRUP need categories</h2></div><Badge tone="info">Evidence matching only</Badge></div>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Need categories</p><div className="mt-3 flex flex-wrap gap-2">{match.needCategories.map((category) => <Badge key={category}>{category}</Badge>)}</div></div>
          <div className="rounded-md border border-slate-200 bg-white p-4"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Keywords</p><div className="mt-3 flex flex-wrap gap-2">{product.keywords.map((keyword) => <Badge key={keyword}>{keyword}</Badge>)}</div></div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Matched institutions</p><h2 className="mt-1 text-base font-semibold text-slate-950">{match.matchedInstitutions.length.toLocaleString("id-ID")} institutions matched</h2><p className="mt-1 text-sm text-slate-600">Rows link to institution workspaces for evidence review.</p></div>
            <Link href="/products" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Back to Products</Link>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1080px] border-collapse text-left text-sm">
            <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400"><tr><th className="border-b border-slate-200 px-5 py-3">Institution</th><th className="border-b border-slate-200 px-5 py-3">Region</th><th className="border-b border-slate-200 px-5 py-3">Need categories</th><th className="border-b border-slate-200 px-5 py-3">Packages</th><th className="border-b border-slate-200 px-5 py-3">Pagu</th><th className="border-b border-slate-200 px-5 py-3">Workspace</th></tr></thead>
            <tbody className="divide-y divide-slate-200/80 bg-white">
              {institutions.map((institution) => (
                <tr key={institution.institution_id} className="align-top">
                  <td className="max-w-[320px] px-5 py-4"><p className="font-medium text-slate-950">{institution.institution_display_name}</p><p className="mt-1 text-xs leading-5 text-slate-500">{institution.parent_organization || institution.work_unit}</p></td>
                  <td className="px-5 py-4 text-slate-600">{institution.province_or_region || "Not provided"}</td>
                  <td className="max-w-[260px] px-5 py-4 text-slate-600">{institution.relevant_categories}</td>
                  <td className="px-5 py-4 text-slate-700">{institution.total_relevant_packages.toLocaleString("id-ID")}</td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-700">{formatIdr(institution.total_pagu)}</td>
                  <td className="px-5 py-4"><Link href={`/institutions/${institution.institution_id}`} className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50">Open Workspace</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="p-5 md:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Example packages from SiRUP</p>
        <h2 className="mt-2 text-base font-semibold text-slate-950">Planning examples</h2>
        {examplePackages.length > 0 ? (
          <ul className="mt-4 grid gap-3 lg:grid-cols-2">
            {examplePackages.map((example) => <li key={`${example.institutionId}-${example.packageName}`} className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-700"><p className="font-medium text-slate-950">{example.packageName}</p><Link href={`/institutions/${example.institutionId}`} className="mt-2 inline-flex text-xs font-medium text-blue-700 hover:underline">{example.institutionName}</Link></li>)}
          </ul>
        ) : <p className="mt-4 text-sm leading-6 text-slate-600">No example package names are available for this product match.</p>}
      </Card>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return <div><dt className="font-medium text-slate-950">{label}</dt><dd className="mt-1 break-words">{value || "Not available"}</dd></div>;
}
