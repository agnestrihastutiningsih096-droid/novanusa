"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { formatIdr } from "@/lib/institution-utils";
import type { NeedCategory, ProductRecord } from "@/lib/product-intelligence";

type ProductTableRow = { product: ProductRecord; needCategories: NeedCategory[]; matchedInstitutionCount: number; matchedPagu: number };

type ProductsClientProps = { rows: ProductTableRow[] };

export default function ProductsClient({ rows }: ProductsClientProps) {
  const router = useRouter();
  const [provider, setProvider] = useState("ALL");
  const [brand, setBrand] = useState("ALL");
  const [category, setCategory] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [query, setQuery] = useState("");

  const providers = useMemo(() => Array.from(new Set(rows.map((row) => row.product.providerName))).sort(), [rows]);
  const brands = useMemo(() => Array.from(new Set(rows.map((row) => row.product.brand))).sort(), [rows]);
  const categories = useMemo(() => Array.from(new Set(rows.map((row) => row.product.productCategory))).sort(), [rows]);
  const statuses = useMemo(() => Array.from(new Set(rows.map((row) => row.product.status))).sort(), [rows]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return rows.filter((row) => {
      const product = row.product;
      const searchText = [product.providerName, product.principalName, product.brand, product.productName, product.productCategory, product.productSubcategory, product.keywords.join(" "), product.status].join(" ").toLowerCase();
      return (provider === "ALL" || product.providerName === provider) && (brand === "ALL" || product.brand === brand) && (category === "ALL" || product.productCategory === category) && (status === "ALL" || product.status === status) && (!normalizedQuery || searchText.includes(normalizedQuery));
    });
  }, [brand, category, provider, query, rows, status]);

  function openProduct(productId: string) {
    router.push(`/products/${productId}`);
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Product table</p>
              <h2 className="mt-1 text-base font-semibold text-slate-950">{filteredRows.length.toLocaleString("id-ID")} products shown</h2>
              <p className="mt-1 text-sm text-slate-600">SiRUP Planning Evidence Only. Product data pending INAPROC verification. No tender status inferred.</p>
            </div>
            <Badge tone="info">Evidence matching only</Badge>
          </div>
          <div className="grid gap-3 lg:grid-cols-[1.3fr_0.9fr_0.9fr_0.9fr_1.1fr]">
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Search
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search product, keyword, brand, category..." className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" />
            </label>
            <FilterSelect label="Provider" value={provider} options={providers} allLabel="All providers" onChange={setProvider} />
            <FilterSelect label="Brand" value={brand} options={brands} allLabel="All brands" onChange={setBrand} />
            <FilterSelect label="Category" value={category} options={categories} allLabel="All categories" onChange={setCategory} />
            <FilterSelect label="Status" value={status} options={statuses} allLabel="All statuses" onChange={setStatus} />
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1480px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
            <tr>
              <th className="border-b border-slate-200 px-5 py-3">Provider</th>
              <th className="border-b border-slate-200 px-5 py-3">Principal/Brand</th>
              <th className="border-b border-slate-200 px-5 py-3">Product</th>
              <th className="border-b border-slate-200 px-5 py-3">Category</th>
              <th className="border-b border-slate-200 px-5 py-3">Keywords</th>
              <th className="border-b border-slate-200 px-5 py-3">Matched Institutions</th>
              <th className="border-b border-slate-200 px-5 py-3">Matched Pagu</th>
              <th className="border-b border-slate-200 px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200/80 bg-white">
            {filteredRows.map((row) => (
              <tr key={row.product.id} role="link" tabIndex={0} onClick={() => openProduct(row.product.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openProduct(row.product.id); } }} className="cursor-pointer align-top transition-colors hover:bg-slate-50/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-blue-300">
                <td className="px-5 py-4"><p className="font-medium text-slate-950">{row.product.providerName}</p><p className="mt-1 text-xs text-slate-500">{row.product.providerType}</p></td>
                <td className="max-w-[240px] px-5 py-4 text-slate-600"><p>{row.product.principalName}</p><p className="mt-1 font-medium text-slate-800">{row.product.brand}</p></td>
                <td className="max-w-[260px] px-5 py-4"><Link href={`/products/${row.product.id}`} onClick={(event) => event.stopPropagation()} className="font-medium text-slate-950 underline-offset-4 hover:text-blue-700 hover:underline">{row.product.productName}</Link><p className="mt-1 text-xs leading-5 text-slate-500">{row.product.productSubcategory}</p></td>
                <td className="px-5 py-4"><div className="flex flex-wrap gap-2">{row.needCategories.map((item) => <Badge key={item}>{item}</Badge>)}</div></td>
                <td className="max-w-[280px] px-5 py-4 text-slate-600">{row.product.keywords.join(", ")}</td>
                <td className="px-5 py-4 text-slate-700">{row.matchedInstitutionCount.toLocaleString("id-ID")}</td>
                <td className="whitespace-nowrap px-5 py-4 text-slate-700">{formatIdr(row.matchedPagu)}</td>
                <td className="px-5 py-4"><Badge tone="warning">{row.product.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-slate-200/80 px-5 py-4 text-sm text-slate-600 md:px-6">
        {filteredRows.length === 0 ? "No products match the current filters." : `${filteredRows.length.toLocaleString("id-ID")} visible of ${rows.length.toLocaleString("id-ID")} seeded product records.`}
      </div>
    </Card>
  );
}

function FilterSelect({ label, value, options, allLabel, onChange }: { label: string; value: string; options: string[]; allLabel: string; onChange: (value: string) => void }) {
  return (
    <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
        <option value="ALL">{allLabel}</option>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  );
}
