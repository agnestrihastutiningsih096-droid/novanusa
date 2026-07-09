import { loadProspects, splitExamples, splitList, type Prospect } from "@/lib/institution-data";
import { readStoredProducts } from "@/lib/product-store";

export type NeedCategory = "LAPTOP" | "PRINTER" | "SCANNER" | "CCTV" | "NETWORKING" | "SERVER" | "STORAGE" | "UPS" | "CAMERA_VIDEO" | "OFFICE_FURNITURE" | "IT_HARDWARE";
export type EvidenceSource = "MANUAL_SEED_V1" | "INAPROC_PENDING_VERIFICATION" | "INAPROC_SYNC_V1";
export type ProductStatus = "PRODUCT_DATA_PENDING_INAPROC_VERIFICATION" | "SYNCED_PENDING_VERIFICATION";

export type ProductEntity = {
  id: string;
  name: string;
  provider: string;
  principal: string;
  brand: string;
  category: NeedCategory;
  subcategory: string;
  price: string;
  tkdn: string;
  certificate: string;
  specification: string;
  source_url: string;
  photo_url: string;
  keywords: string[];
  evidence_status: EvidenceSource;
  source: string;
  synced_at: string;
  status: ProductStatus;
};

export type ProductRecord = ProductEntity & {
  providerName: string;
  providerType: string;
  principalName: string;
  productName: string;
  productCategory: NeedCategory;
  productSubcategory: string;
  evidenceSource: EvidenceSource;
  sourceUrl: string;
  priceInfo: string;
};

export type ProductDataSet = {
  products: ProductRecord[];
  source: string;
  evidence_status: EvidenceSource;
  synced_at: string;
  usingSeedFallback: boolean;
};

export type ProductMatch = {
  product: ProductRecord;
  needCategories: NeedCategory[];
  matchedInstitutions: Prospect[];
  matchedPagu: number;
  examplePackages: Array<{ institutionId: string; institutionName: string; packageName: string }>;
};

const pendingStatus = "PRODUCT_DATA_PENDING_INAPROC_VERIFICATION";
const seedSyncedAt = "MANUAL_SEED_V1";
const baseSeed = {
  provider: "Mitracom",
  principal: "Pending principal verification",
  brand: "Generic",
  price: "Pending INAPROC/e-Katalog verification",
  tkdn: "Pending verification",
  certificate: "Pending verification",
  specification: "Generic product category seed for SiRUP need matching.",
  source_url: "",
  photo_url: "",
  evidence_status: "MANUAL_SEED_V1" as EvidenceSource,
  source: "MANUAL_SEED_V1",
  synced_at: seedSyncedAt,
  status: pendingStatus as ProductStatus,
};

function withAliases(product: ProductEntity, providerType = "Provider"): ProductRecord {
  return {
    ...product,
    providerName: product.provider,
    providerType,
    principalName: product.principal,
    productName: product.name,
    productCategory: product.category,
    productSubcategory: product.subcategory,
    evidenceSource: product.evidence_status,
    sourceUrl: product.source_url,
    priceInfo: product.price,
  };
}

export function normalizeProduct(product: ProductEntity): ProductRecord {
  return withAliases({
    ...product,
    keywords: Array.isArray(product.keywords) ? product.keywords : [],
    evidence_status: product.evidence_status || "INAPROC_PENDING_VERIFICATION",
    source: product.source || "INAPROC_SYNC_V1",
    synced_at: product.synced_at || new Date().toISOString(),
  });
}

export const seedProductRecords: ProductRecord[] = [
  withAliases({ ...baseSeed, id: "mitracom-laptop-general", name: "Business laptop and notebook", category: "LAPTOP", subcategory: "Notebook, laptop 2-in-1, mobile workstation", keywords: ["laptop", "notebook", "2in1", "komputer jinjing"] }),
  withAliases({ ...baseSeed, id: "mitracom-printer-general", name: "Office printer and multifunction printer", category: "PRINTER", subcategory: "Printer A4/A3, printer scanner, all-in-one", keywords: ["printer", "all in one", "multifunction", "a4", "a3"] }),
  withAliases({ ...baseSeed, id: "mitracom-scanner-general", name: "Document scanner", category: "SCANNER", subcategory: "Flatbed, ADF, document scanner", keywords: ["scanner", "pemindai", "scan dokumen", "adf"] }),
  withAliases({ ...baseSeed, id: "mitracom-cctv-general", name: "CCTV camera and recorder system", category: "CCTV", subcategory: "IP camera, NVR, surveillance accessories", keywords: ["cctv", "surveillance", "kamera pengawas", "nvr"] }),
  withAliases({ ...baseSeed, id: "mitracom-networking-general", name: "Network equipment", category: "NETWORKING", subcategory: "Switch, router, access point, structured cabling", keywords: ["network", "networking", "switch", "router", "access point", "jaringan"] }),
  withAliases({ ...baseSeed, id: "mitracom-server-general", name: "Server hardware", category: "SERVER", subcategory: "Rack server, tower server, server accessories", keywords: ["server", "rack server", "tower server"] }),
  withAliases({ ...baseSeed, id: "mitracom-ups-general", name: "Uninterruptible power supply", category: "UPS", subcategory: "UPS desktop, rack UPS, power backup", keywords: ["ups", "uninterruptible power supply", "backup power", "catu daya"] }),
  withAliases({ ...baseSeed, id: "mitracom-storage-general", name: "Data storage equipment", category: "STORAGE", subcategory: "NAS, external storage, storage drive", keywords: ["storage", "nas", "hard disk", "ssd", "penyimpanan"] }),
  withAliases({ ...baseSeed, id: "mitracom-camera-video-general", name: "Camera and video equipment", category: "CAMERA_VIDEO", subcategory: "Camera, video conference, audio visual", keywords: ["camera", "kamera", "video", "webcam", "conference"] }),
  withAliases({ ...baseSeed, id: "mitracom-office-furniture-general", name: "Office furniture", category: "OFFICE_FURNITURE", subcategory: "Office desk, office chair, cabinet, workstation furniture", keywords: ["furniture", "meja", "kursi", "lemari", "mebel"] }),
];

export const productRecords = seedProductRecords;

const categoryAliases: Record<NeedCategory, NeedCategory[]> = {
  LAPTOP: ["LAPTOP", "IT_HARDWARE"],
  PRINTER: ["PRINTER", "IT_HARDWARE"],
  SCANNER: ["SCANNER", "IT_HARDWARE"],
  CCTV: ["CCTV", "IT_HARDWARE"],
  NETWORKING: ["NETWORKING", "IT_HARDWARE"],
  SERVER: ["SERVER", "IT_HARDWARE"],
  STORAGE: ["STORAGE", "IT_HARDWARE"],
  UPS: ["UPS", "IT_HARDWARE"],
  CAMERA_VIDEO: ["CAMERA_VIDEO", "IT_HARDWARE"],
  OFFICE_FURNITURE: ["OFFICE_FURNITURE"],
  IT_HARDWARE: ["IT_HARDWARE"],
};

function includesKeyword(prospect: Prospect, keywords: string[]) {
  const haystack = `${prospect.relevant_categories} ${prospect.example_package_names}`.toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
}

export function getProductNeedCategories(product: ProductRecord) {
  return categoryAliases[product.productCategory];
}

export function loadProductDataSet(): ProductDataSet {
  const storedProducts = readStoredProducts();
  if (storedProducts.length > 0) {
    const products = storedProducts.map(normalizeProduct);
    const latestSync = products.map((product) => product.synced_at).sort().at(-1) ?? "";
    return {
      products,
      source: "INAPROC_SYNC_V1",
      evidence_status: "INAPROC_PENDING_VERIFICATION",
      synced_at: latestSync,
      usingSeedFallback: false,
    };
  }

  return {
    products: seedProductRecords,
    source: "MANUAL_SEED_V1",
    evidence_status: "INAPROC_PENDING_VERIFICATION",
    synced_at: seedSyncedAt,
    usingSeedFallback: true,
  };
}

export function matchProductToProspects(product: ProductRecord, prospects = loadProspects()): ProductMatch {
  const needCategories = getProductNeedCategories(product);
  const matchedInstitutions = prospects.filter((prospect) => {
    const prospectCategories = splitList(prospect.relevant_categories) as NeedCategory[];
    return prospectCategories.some((category) => needCategories.includes(category)) || includesKeyword(prospect, product.keywords);
  });

  return {
    product,
    needCategories,
    matchedInstitutions,
    matchedPagu: matchedInstitutions.reduce((sum, prospect) => sum + prospect.total_pagu, 0),
    examplePackages: matchedInstitutions.flatMap((institution) =>
      splitExamples(institution.example_package_names).slice(0, 3).map((packageName) => ({
        institutionId: institution.institution_id,
        institutionName: institution.institution_display_name,
        packageName,
      })),
    ),
  };
}

export function getProductMatches(prospects = loadProspects()) {
  return loadProductDataSet().products.map((product) => matchProductToProspects(product, prospects));
}

export function getProductMatchesWithDataSet(prospects = loadProspects()) {
  const dataSet = loadProductDataSet();
  return {
    dataSet,
    matches: dataSet.products.map((product) => matchProductToProspects(product, prospects)),
  };
}

export function findProductById(id: string) {
  return loadProductDataSet().products.find((product) => product.id === id) ?? seedProductRecords.find((product) => product.id === id);
}
