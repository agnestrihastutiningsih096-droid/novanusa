import { loadProspects, splitExamples, splitList, type Prospect } from "@/lib/institution-data";

export type NeedCategory = "LAPTOP" | "PRINTER" | "SCANNER" | "CCTV" | "NETWORKING" | "SERVER" | "STORAGE" | "UPS" | "CAMERA_VIDEO" | "OFFICE_FURNITURE" | "IT_HARDWARE";
export type EvidenceSource = "MANUAL_SEED_V1" | "INAPROC_PENDING_VERIFICATION";
export type ProductStatus = "PRODUCT_DATA_PENDING_INAPROC_VERIFICATION";

export type ProductRecord = {
  id: string;
  providerName: string;
  providerType: string;
  principalName: string;
  brand: string;
  productName: string;
  productCategory: NeedCategory;
  productSubcategory: string;
  keywords: string[];
  evidenceSource: EvidenceSource;
  sourceUrl: string;
  tkdn: string;
  priceInfo: string;
  status: ProductStatus;
};

export type ProductMatch = {
  product: ProductRecord;
  needCategories: NeedCategory[];
  matchedInstitutions: Prospect[];
  matchedPagu: number;
  examplePackages: Array<{ institutionId: string; institutionName: string; packageName: string }>;
};

const pendingStatus = "PRODUCT_DATA_PENDING_INAPROC_VERIFICATION";
const baseProduct = {
  providerName: "Mitracom",
  providerType: "Provider",
  principalName: "Pending principal verification",
  brand: "Generic",
  evidenceSource: "MANUAL_SEED_V1" as const,
  sourceUrl: "",
  tkdn: "Pending verification",
  priceInfo: "Pending INAPROC/e-Katalog verification",
  status: pendingStatus as ProductStatus,
};

export const productRecords: ProductRecord[] = [
  { ...baseProduct, id: "mitracom-laptop-general", productName: "Business laptop and notebook", productCategory: "LAPTOP", productSubcategory: "Notebook, laptop 2-in-1, mobile workstation", keywords: ["laptop", "notebook", "2in1", "komputer jinjing"] },
  { ...baseProduct, id: "mitracom-printer-general", productName: "Office printer and multifunction printer", productCategory: "PRINTER", productSubcategory: "Printer A4/A3, printer scanner, all-in-one", keywords: ["printer", "all in one", "multifunction", "a4", "a3"] },
  { ...baseProduct, id: "mitracom-scanner-general", productName: "Document scanner", productCategory: "SCANNER", productSubcategory: "Flatbed, ADF, document scanner", keywords: ["scanner", "pemindai", "scan dokumen", "adf"] },
  { ...baseProduct, id: "mitracom-cctv-general", productName: "CCTV camera and recorder system", productCategory: "CCTV", productSubcategory: "IP camera, NVR, surveillance accessories", keywords: ["cctv", "surveillance", "kamera pengawas", "nvr"] },
  { ...baseProduct, id: "mitracom-networking-general", productName: "Network equipment", productCategory: "NETWORKING", productSubcategory: "Switch, router, access point, structured cabling", keywords: ["network", "networking", "switch", "router", "access point", "jaringan"] },
  { ...baseProduct, id: "mitracom-server-general", productName: "Server hardware", productCategory: "SERVER", productSubcategory: "Rack server, tower server, server accessories", keywords: ["server", "rack server", "tower server"] },
  { ...baseProduct, id: "mitracom-ups-general", productName: "Uninterruptible power supply", productCategory: "UPS", productSubcategory: "UPS desktop, rack UPS, power backup", keywords: ["ups", "uninterruptible power supply", "backup power", "catu daya"] },
  { ...baseProduct, id: "mitracom-storage-general", productName: "Data storage equipment", productCategory: "STORAGE", productSubcategory: "NAS, external storage, storage drive", keywords: ["storage", "nas", "hard disk", "ssd", "penyimpanan"] },
  { ...baseProduct, id: "mitracom-camera-video-general", productName: "Camera and video equipment", productCategory: "CAMERA_VIDEO", productSubcategory: "Camera, video conference, audio visual", keywords: ["camera", "kamera", "video", "webcam", "conference"] },
  { ...baseProduct, id: "mitracom-office-furniture-general", productName: "Office furniture", productCategory: "OFFICE_FURNITURE", productSubcategory: "Office desk, office chair, cabinet, workstation furniture", keywords: ["furniture", "meja", "kursi", "lemari", "mebel"] },
];

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
  return productRecords.map((product) => matchProductToProspects(product, prospects));
}

export function findProductById(id: string) {
  return productRecords.find((product) => product.id === id);
}
