"use client";

import { useState } from "react";
import { operatorHeaders } from "@/lib/operator-auth";
import type { ContactVerificationRecord } from "@/lib/contact-verification";
import { useInstitutionOperator } from "./InstitutionOperatorContext";

type Props = {
  institutionId: string;
  contactEmail: string;
  evidenceUrl: string;
  expectedContactFingerprint: string | null;
  verificationSource: "OFFICIAL_INSTITUTION_WEBSITE";
  initialVerification: ContactVerificationRecord | null;
};

export default function ContactVerificationAction(props: Props) {
  const { operatorToken, operatorReady } = useInstitutionOperator();
  const [confirmed, setConfirmed] = useState(false);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [verification, setVerification] = useState<ContactVerificationRecord | null>(props.initialVerification);

  async function verifyContact() {
    if (!operatorReady || !props.expectedContactFingerprint || !confirmed) return;
    setSubmitting(true);
    setMessage("Memverifikasi...");
    try {
      const response = await fetch(`/api/institutions/${encodeURIComponent(props.institutionId)}/contact-verification`, {
        method: "POST",
        headers: operatorHeaders(operatorToken),
        body: JSON.stringify({
          confirm: true,
          expectedContactFingerprint: props.expectedContactFingerprint,
          verificationSource: props.verificationSource,
        }),
      });
      const payload = await response.json() as { ok?: boolean; verification?: ContactVerificationRecord; idempotent?: boolean; error?: { code?: string; message?: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.code ?? payload.error?.message ?? "CONTACT_VERIFICATION_FAILED");
      if (!payload.verification) throw new Error("CONTACT_VERIFICATION_RESPONSE_INVALID");
      setVerification(payload.verification);
      setMessage(payload.idempotent ? "Kontak sudah terverifikasi dengan bukti yang sama." : "Kontak berhasil diverifikasi.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "CONTACT_VERIFICATION_FAILED");
    } finally {
      setSubmitting(false);
    }
  }

  const validContact = Boolean(props.contactEmail && props.evidenceUrl && props.expectedContactFingerprint);

  if (verification) {
    return (
      <div className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">VERIFIED</p>
        <dl className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
          <div><dt className="font-medium text-slate-950">Diverifikasi pada</dt><dd>{new Intl.DateTimeFormat("id-ID", { dateStyle: "medium", timeStyle: "short" }).format(new Date(verification.verifiedAt))}</dd></div>
          <div><dt className="font-medium text-slate-950">Diverifikasi oleh</dt><dd>{verification.verifiedBy}</dd></div>
          <div><dt className="font-medium text-slate-950">Sumber verifikasi</dt><dd>{verification.verificationSource}</dd></div>
        </dl>
      </div>
    );
  }

  return (
    <div className="mt-5 rounded-md border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Verifikasi Kontak</p>
      <dl className="mt-3 space-y-2 text-sm leading-6 text-slate-700">
        <div><dt className="font-medium text-slate-950">Email kontak</dt><dd className="break-all">{props.contactEmail || "Tidak tersedia"}</dd></div>
        <div><dt className="font-medium text-slate-950">URL bukti</dt><dd className="break-all">{props.evidenceUrl || "Tidak tersedia"}</dd></div>
        <div><dt className="font-medium text-slate-950">Sumber verifikasi</dt><dd>{props.verificationSource}</dd></div>
      </dl>
      <label className="mt-3 flex items-start gap-2 text-sm leading-5 text-slate-700">
        <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-1" />
        <span>Saya mengonfirmasi bahwa email di atas tercantum pada URL bukti institusi resmi tersebut.</span>
      </label>
      <button type="button" onClick={verifyContact} disabled={!operatorReady || !confirmed || !validContact || submitting} className="mt-3 h-9 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50">
        {submitting ? "Memverifikasi..." : "Verifikasi Kontak"}
      </button>
      <p className="mt-2 text-xs leading-5 text-slate-500">{message || (!operatorReady ? "Aktifkan operator pada kontrol draf untuk memverifikasi." : "Verifikasi berlaku hanya untuk email dan URL bukti yang ditampilkan.")}</p>
    </div>
  );
}
