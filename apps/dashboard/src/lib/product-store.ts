import fs from "fs";
import path from "path";
import type { ProductEntity } from "@/lib/product-intelligence";

export const productStorePath = path.resolve(process.cwd(), "data", "product-intelligence", "products.json");

type ProductStoreFile = {
  products: ProductEntity[];
};

function ensureStoreDirectory() {
  fs.mkdirSync(path.dirname(productStorePath), { recursive: true });
}

function readStoreFile(): ProductStoreFile {
  if (!fs.existsSync(productStorePath)) {
    return { products: [] };
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(productStorePath, "utf8")) as Partial<ProductStoreFile>;
    return { products: Array.isArray(parsed.products) ? parsed.products : [] };
  } catch {
    return { products: [] };
  }
}

export function readStoredProducts() {
  return readStoreFile().products;
}

export function upsertProducts(products: ProductEntity[]) {
  ensureStoreDirectory();
  const existing = readStoreFile().products;
  const byId = new Map(existing.map((product) => [product.id, product]));
  let inserted = 0;
  let updated = 0;

  for (const product of products) {
    if (byId.has(product.id)) {
      updated += 1;
    } else {
      inserted += 1;
    }
    byId.set(product.id, product);
  }

  const nextProducts = Array.from(byId.values()).sort((left, right) => left.name.localeCompare(right.name));
  fs.writeFileSync(productStorePath, JSON.stringify({ products: nextProducts }, null, 2));

  return {
    inserted,
    updated,
    total: nextProducts.length,
  };
}
