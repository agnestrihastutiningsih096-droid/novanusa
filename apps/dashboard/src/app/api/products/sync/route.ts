import { crawlInaprocProducts } from "@/lib/inaproc-crawler";
import { upsertProducts } from "@/lib/product-store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const syncResult = await crawlInaprocProducts();
    const writeResult = upsertProducts(syncResult.products);

    return Response.json({
      ok: true,
      inserted: writeResult.inserted,
      updated: writeResult.updated,
      total: writeResult.total,
      source: syncResult.source,
      evidence_status: syncResult.evidence_status,
      synced_at: syncResult.synced_at,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Product sync failed.";
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
}
