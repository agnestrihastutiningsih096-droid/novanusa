import type { NeedCategory, ProductEntity } from "@/lib/product-intelligence";

export type InaprocSyncResult = {
  products: ProductEntity[];
  source: string;
  evidence_status: "INAPROC_PENDING_VERIFICATION";
  synced_at: string;
};

type RawInaprocProduct = Record<string, unknown>;

const fallbackCategories: Array<{ category: NeedCategory; name: string; keywords: string[]; subcategory: string }> = [
  { category: "LAPTOP", name: "INAPROC pending laptop catalog sample", keywords: ["laptop", "notebook"], subcategory: "Laptop and notebook" },
  { category: "PRINTER", name: "INAPROC pending printer catalog sample", keywords: ["printer", "multifunction"], subcategory: "Printer and multifunction device" },
  { category: "SCANNER", name: "INAPROC pending scanner catalog sample", keywords: ["scanner", "pemindai"], subcategory: "Document scanner" },
  { category: "CCTV", name: "INAPROC pending CCTV catalog sample", keywords: ["cctv", "kamera pengawas"], subcategory: "CCTV and surveillance" },
  { category: "NETWORKING", name: "INAPROC pending networking catalog sample", keywords: ["networking", "switch", "router", "jaringan"], subcategory: "Network equipment" },
  { category: "SERVER", name: "INAPROC pending server catalog sample", keywords: ["server", "rack server"], subcategory: "Server hardware" },
  { category: "UPS", name: "INAPROC pending UPS catalog sample", keywords: ["ups", "catu daya"], subcategory: "Power backup" },
  { category: "STORAGE", name: "INAPROC pending storage catalog sample", keywords: ["storage", "nas", "ssd"], subcategory: "Storage equipment" },
  { category: "CAMERA_VIDEO", name: "INAPROC pending camera video catalog sample", keywords: ["camera", "kamera", "video"], subcategory: "Camera and video equipment" },
  { category: "OFFICE_FURNITURE", name: "INAPROC pending office furniture catalog sample", keywords: ["meja", "kursi", "mebel"], subcategory: "Office furniture" },
];

function asText(value: unknown) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return value.toString();
  return "";
}

function slug(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 90) || "product";
}

function inferCategory(value: string): NeedCategory {
  const text = value.toLowerCase();
  if (text.includes("printer")) return "PRINTER";
  if (text.includes("scanner") || text.includes("pemindai")) return "SCANNER";
  if (text.includes("cctv")) return "CCTV";
  if (text.includes("network") || text.includes("switch") || text.includes("router") || text.includes("jaringan")) return "NETWORKING";
  if (text.includes("server")) return "SERVER";
  if (text.includes("storage") || text.includes("nas") || text.includes("ssd")) return "STORAGE";
  if (text.includes("ups")) return "UPS";
  if (text.includes("camera") || text.includes("kamera") || text.includes("video")) return "CAMERA_VIDEO";
  if (text.includes("meja") || text.includes("kursi") || text.includes("furniture") || text.includes("mebel")) return "OFFICE_FURNITURE";
  if (text.includes("laptop") || text.includes("notebook")) return "LAPTOP";
  return "IT_HARDWARE";
}

function normalizeRawProduct(raw: RawInaprocProduct, syncedAt: string): ProductEntity {
  const name = asText(raw.name ?? raw.productName ?? raw.nama_produk ?? raw.product_name) || "INAPROC product pending verification";
  const categoryText = `${name} ${asText(raw.category ?? raw.kategori)} ${asText(raw.subcategory ?? raw.subkategori)}`;
  const category = inferCategory(categoryText);

  return {
    id: asText(raw.id ?? raw.product_id ?? raw.kode_produk) || `inaproc-${slug(name)}`,
    name,
    provider: asText(raw.provider ?? raw.providerName ?? raw.nama_penyedia) || "Pending provider verification",
    principal: asText(raw.principal ?? raw.principalName ?? raw.nama_prinsipal) || "Pending principal verification",
    brand: asText(raw.brand ?? raw.merek) || "Pending brand verification",
    category,
    subcategory: asText(raw.subcategory ?? raw.subkategori) || category,
    price: asText(raw.price ?? raw.harga) || "Pending price verification",
    tkdn: asText(raw.tkdn) || "Pending TKDN verification",
    certificate: asText(raw.certificate ?? raw.sertifikat) || "Pending certificate verification",
    specification: asText(raw.specification ?? raw.spesifikasi) || "Pending specification verification",
    source_url: asText(raw.source_url ?? raw.url) || "https://katalog.inaproc.id/",
    photo_url: asText(raw.photo_url ?? raw.image ?? raw.foto),
    keywords: Array.from(new Set([category.toLowerCase(), ...name.toLowerCase().split(/[^a-z0-9]+/).filter((item) => item.length > 2)])),
    evidence_status: "INAPROC_PENDING_VERIFICATION",
    source: "INAPROC_SYNC_V1",
    synced_at: syncedAt,
    status: "SYNCED_PENDING_VERIFICATION",
  };
}

function fallbackProducts(syncedAt: string): ProductEntity[] {
  return fallbackCategories.map((item) => ({
    id: `inaproc-pending-${item.category.toLowerCase().replace("_", "-")}`,
    name: item.name,
    provider: "Pending provider verification",
    principal: "Pending principal verification",
    brand: "Pending brand verification",
    category: item.category,
    subcategory: item.subcategory,
    price: "Pending INAPROC verification",
    tkdn: "Pending TKDN verification",
    certificate: "Pending certificate verification",
    specification: "Deterministic adapter fallback record. Live INAPROC response was unavailable or not parseable during sync.",
    source_url: "https://katalog.inaproc.id/",
    photo_url: "",
    keywords: item.keywords,
    evidence_status: "INAPROC_PENDING_VERIFICATION",
    source: "INAPROC_ADAPTER_FALLBACK_V1",
    synced_at: syncedAt,
    status: "SYNCED_PENDING_VERIFICATION",
  }));
}

async function fetchInaprocProducts(syncedAt: string) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch("https://katalog.inaproc.id/", {
      headers: { accept: "application/json,text/html;q=0.9,*/*;q=0.8" },
      signal: controller.signal,
    });

    if (!response.ok) return [];
    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) return [];

    const payload = (await response.json()) as unknown;
    const rows = Array.isArray(payload) ? payload : Array.isArray((payload as { data?: unknown }).data) ? ((payload as { data: RawInaprocProduct[] }).data) : [];
    return rows.slice(0, 50).map((row) => normalizeRawProduct(row, syncedAt));
  } catch {
    return [];
  } finally {
    clearTimeout(timeout);
  }
}

export async function crawlInaprocProducts(): Promise<InaprocSyncResult> {
  const synced_at = new Date().toISOString();
  const liveProducts = await fetchInaprocProducts(synced_at);
  const products = liveProducts.length > 0 ? liveProducts : fallbackProducts(synced_at);

  return {
    products,
    source: liveProducts.length > 0 ? "INAPROC_SYNC_V1" : "INAPROC_ADAPTER_FALLBACK_V1",
    evidence_status: "INAPROC_PENDING_VERIFICATION",
    synced_at,
  };
}
