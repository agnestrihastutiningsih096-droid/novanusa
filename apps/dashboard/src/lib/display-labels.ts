import type { DraftWorkflowStatus } from "@/lib/workflow-state-types";

export const draftStatusLabels: Record<DraftWorkflowStatus, string> = {
  NOT_GENERATED: "Belum Dibuat",
  GENERATED: "Dibuat",
  EDITED: "Diedit",
  SAVED: "Disimpan",
  UNDER_REVIEW: "Dalam Peninjauan",
  APPROVED: "Disetujui",
  READY_TO_SEND: "Siap Dikirim",
  SENT: "Terkirim",
};

const genericStatusLabels: Record<string, string> = {
  NOT_CONTACTED: "Belum Dihubungi",
  DRAFT_GENERATED: "Draf Dibuat",
  DRAFT_EDITED: "Draf Diedit",
  GENERATED: "Dibuat",
  EDITED: "Diedit",
  SAVED: "Disimpan",
  UNDER_REVIEW: "Dalam Peninjauan",
  APPROVED: "Disetujui",
  READY_TO_SEND: "Siap Dikirim",
  SENT: "Terkirim",
  FAILED: "Gagal",
  CONTACT_FOUND: "Kontak Ditemukan",
  CONTACT_NEEDS_REVIEW: "Kontak Perlu Ditinjau",
  CONTACT_MISSING: "Kontak Belum Ada",
  READY_FOR_CONTACT_SEARCH: "Siap Ditindaklanjuti",
  NEEDS_REVIEW: "Perlu Ditinjau",
  SIRUP_PLANNING_ONLY: "Bukti Perencanaan SiRUP",
  SPSE_NOT_CHECKED_NATIONALLY: "SPSE Belum Dicek Nasional",
  INAPROC_PENDING_VERIFICATION: "Menunggu Verifikasi INAPROC",
  MANUAL_SEED_V1: "Data Awal Manual",
  not_sent: "Belum Dikirim",
  sent: "Terkirim",
  failed: "Gagal",
};

export function labelForStatus(value: string | null | undefined) {
  if (!value) return "Tidak Tersedia";
  return genericStatusLabels[value] ?? value;
}

export function labelForOptional(value: string | null | undefined) {
  return value?.trim() ? value : "Tidak tersedia";
}

