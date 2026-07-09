"use client";

import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { formatIdr } from "@/lib/institution-utils";
import type { NeedCategory, ProductDataSet, ProductRecord } from "@/lib/product-intelligence";

type ProductTableRow = { product: ProductRecord; needCategories: NeedCategory[]; matchedInstitutionCount: number; matchedPagu: number };
type SyncResponse = { ok: true; inserted: number; updated: number; total: number; source: string; evidence_status: string; synced_at: string } | { ok: false; error: string };
type ProductsClientProps = { rows: ProductTableRow[]; dataSource: ProductDataSet };

export default function ProductsClient({ rows, dataSource }: ProductsClientProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [provider, setProvider] = useState("ALL");
  const [brand, setBrand] = useState("ALL");
  const [category, setCategory] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [query, setQuery] = useState("");
  const [syncMessage, setSyncMessage] = useState("");
  const [syncError, setSyncError] = useState("");
  const [syncing, setSyncing] = useState(false);

  const providers = useMemo(() => Array.from(new Set(rows.map((row) => row.product.providerName))).sort(), [rows]);
  const brands = useMemo(() => Array.from(new Set(rows.map((row) => row.product.brand))).sort(), [rows]);
  const categories = useMemo(() => Array.from(new Set(rows.map((row) => row.product.productCategory))).sort(), [rows]);
  const statuses = useMemo(() => Array.from(new Set(rows.map((row) => row.product.status))).sort(), [rows]);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return rows.filter((row) => {
      const product = row.product;
      const searchText = [product.providerName, product.principalName, product.brand, product.productName, product.productCategory, product.productSubcategory, product.keywords.join(" "), product.status, product.source, product.evidence_status].join(" ").toLowerCase();
      return (provider === "ALL" || product.providerName === provider) && (brand === "ALL" || product.brand === brand) && (category === "ALL" || product.productCategory === category) && (status === "ALL" || product.status === status) && (!normalizedQuery || searchText.includes(normalizedQuery));
    });
  }, [brand, category, provider, query, rows, status]);

  async function syncProducts() {
    setSyncing(true);
    setSyncError("");
    setSyncMessage("");

    try {
      const response = await fetch("/api/products/sync", { method: "POST" });
      const payload = (await response.json()) as SyncResponse;

      if (!response.ok || !payload.ok) {
        throw new Error("error" in payload ? payload.error : "Sinkronisasi produk gagal.");
      }

      setSyncMessage(`Sinkron selesai. Ditambahkan ${payload.inserted.toLocaleString("id-ID")}, diperbarui ${payload.updated.toLocaleString("id-ID")}, total ${payload.total.toLocaleString("id-ID")}.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Sinkronisasi produk gagal.");
    } finally {
      setSyncing(false);
    }
  }

  function openProduct(productId: string) {
    router.push(`/products/${productId}`);
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Tabel produk</p>
              <h2 className="mt-1 text-base font-semibold text-slate-950">{filteredRows.length.toLocaleString("id-ID")} produk ditampilkan</h2>
              <p className="mt-1 text-sm text-slate-600">Hanya bukti perencanaan SiRUP. Data produk menunggu verifikasi INAPROC. Status tender tidak disimpulkan.</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">Sumber saat ini: {dataSource.source}. Disinkronkan pada: {dataSource.synced_at || "Belum sinkron"}.</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <Badge tone={dataSource.usingSeedFallback ? "warning" : "info"}>{dataSource.usingSeedFallback ? "Fallback data awal" : "Store sinkron"}</Badge>
              <button type="button" onClick={syncProducts} disabled={syncing || isPending} className="inline-flex h-9 items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-3 text-sm font-medium text-blue-700 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60">
                {syncing || isPending ? "Menyinkronkan..." : "Sinkronkan Produk"}
              </button>
            </div>
          </div>

          {syncMessage ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{syncMessage}</div> : null}
          {syncError ? <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{syncError}</div> : null}

          <div className="grid gap-3 lg:grid-cols-[1.3fr_0.9fr_0.9fr_0.9fr_1.1fr]">
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Search
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari produk, kata kunci, merek, kategori..." className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100" />
            </label>
            <FilterSelect label="Provider" value={provider} options={providers} allLabel="Semua penyedia" onChange={setProvider} />
            <FilterSelect label="Brand" value={brand} options={brands} allLabel="Semua merek" onChange={setBrand} />
            <FilterSelect label="Category" value={category} options={categories} allLabel="Semua kategori" onChange={setCategory} />
            <FilterSelect label="Status" value={status} options={statuses} allLabel="Semua status" onChange={setStatus} />
          </div>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1600px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
            <tr>
              <th className="border-b border-slate-200 px-5 py-3">Provider</th>
              <th className="border-b border-slate-200 px-5 py-3">Principal/Brand</th>
              <th className="border-b border-slate-200 px-5 py-3">Product</th>
              <th className="border-b border-slate-200 px-5 py-3">Category</th>
              <th className="border-b border-slate-200 px-5 py-3">Keywords</th>
              <th className="border-b border-slate-200 px-5 py-3">Institusi Cocok</th>
              <th className="border-b border-slate-200 px-5 py-3">Pagu Cocok</th>
              <th className="border-b border-slate-200 px-5 py-3">Source</th>
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
                <td className="max-w-[220px] px-5 py-4"><Badge tone={row.product.source === "MANUAL_SEED_V1" ? "warning" : "info"}>{row.product.source}</Badge><p className="mt-2 text-xs leading-5 text-slate-500">{row.product.synced_at}</p></td>
                <td className="px-5 py-4"><Badge tone="warning">{row.product.status}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-slate-200/80 px-5 py-4 text-sm text-slate-600 md:px-6">
        {filteredRows.length === 0 ? "Tidak ada produk yang cocok dengan filter saat ini." : `${filteredRows.length.toLocaleString("id-ID")} visible of ${rows.length.toLocaleString("id-ID")} data produk.`}
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
