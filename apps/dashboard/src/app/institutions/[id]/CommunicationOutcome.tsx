"use client";

import { useEffect, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { fetchLatestGenericCommunicationOutcomeIfActive, sendGenericCommunicationOutcomeIfActive } from "@/lib/communication-outcome-client";
import { COMMUNICATION_OUTCOMES, type CommunicationOutcome as Outcome, type CommunicationOutcomeResult } from "@/lib/communication-outcome";
import { useInstitutionOperator } from "./InstitutionOperatorContext";

type Props = { institutionId: string };
type ErrorPayload = { error?: { code?: string; message?: string; details?: { fields?: string[] } } };

const labels: Record<Outcome, string> = {
  interested: "Tertarik",
  no_decision: "Belum mengambil keputusan",
  not_interested: "Tidak tertarik",
  no_response: "Tidak ada respons",
  invalid_contact: "Kontak tidak valid",
};

export default function CommunicationOutcome({ institutionId }: Props) {
  const { operatorReady, operatorToken } = useInstitutionOperator();
  const [outcome, setOutcome] = useState<Outcome>(COMMUNICATION_OUTCOMES[0]);
  const [note, setNote] = useState("");
  const [latest, setLatest] = useState<CommunicationOutcomeResult["data"] | null>(null);
  const [status, setStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [hydratedKey, setHydratedKey] = useState<string | null>(null);
  const hydrationKey = operatorReady && operatorToken ? `${institutionId}:${operatorToken}` : null;
  const hydrating = hydrationKey !== null && hydratedKey !== hydrationKey;

  useEffect(() => {
    if (!operatorReady || !operatorToken) return;
    let active = true;
    fetchLatestGenericCommunicationOutcomeIfActive(institutionId, operatorToken, operatorReady)!
      .then(async (response) => {
        const payload = await response.json() as { data?: CommunicationOutcomeResult["data"] | null } & ErrorPayload;
        if (!active) return;
        if (!response.ok || !("data" in payload)) {
          const error = payload.error;
          setStatus({ tone: "error", text: `${error?.code ?? "PERSISTENCE_FAILED"}: ${error?.message ?? "Communication outcome could not be recorded."}` });
          return;
        }
        setLatest(payload.data ?? null);
        setStatus(payload.data ? { tone: "success", text: "Communication outcome terbaru dimuat." } : null);
      })
      .catch(() => {
        if (active) setStatus({ tone: "error", text: "PERSISTENCE_FAILED: Communication outcome could not be recorded." });
      })
      .finally(() => {
        if (active) setHydratedKey(`${institutionId}:${operatorToken}`);
      });
    return () => { active = false; };
  }, [institutionId, operatorReady, operatorToken]);

  async function submit() {
    setSubmitting(true);
    setStatus(null);
    try {
      const response = await sendGenericCommunicationOutcomeIfActive(institutionId, operatorToken, operatorReady, outcome, note);
      if (!response) {
        setStatus({ tone: "error", text: "UNAUTHORIZED: Token operator diperlukan." });
        return;
      }
      const commandPayload = await response.json() as CommunicationOutcomeResult | ErrorPayload;
      if (!response.ok || !("data" in commandPayload)) {
        const error = (commandPayload as ErrorPayload).error;
        setStatus({ tone: "error", text: `${error?.code ?? "PERSISTENCE_FAILED"}: ${error?.message ?? "Communication outcome could not be recorded."}` });
        return;
      }
      const latestResponse = await fetchLatestGenericCommunicationOutcomeIfActive(institutionId, operatorToken, operatorReady);
      if (!latestResponse) {
        setStatus({ tone: "error", text: "UNAUTHORIZED: Token operator diperlukan." });
        return;
      }
      const latestPayload = await latestResponse.json() as { data?: CommunicationOutcomeResult["data"] | null } & ErrorPayload;
      if (!latestResponse.ok || !("data" in latestPayload)) {
        const error = latestPayload.error;
        setStatus({ tone: "error", text: `${error?.code ?? "PERSISTENCE_FAILED"}: ${error?.message ?? "Communication outcome could not be recorded."}` });
        return;
      }
      setLatest(latestPayload.data ?? null);
      setNote("");
      setStatus({ tone: "success", text: "Communication outcome berhasil direkam." });
    } catch {
      setStatus({ tone: "error", text: "PERSISTENCE_FAILED: Communication outcome could not be recorded." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Communication Outcome</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Hasil komunikasi institusi</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Rekam hasil komunikasi umum dengan institusi ini. Hasil tidak mengubah workflow atau timeline.</p>
        </div>
        <Badge tone={latest && operatorReady && !hydrating ? "success" : "neutral"}>{latest && operatorReady && !hydrating ? labels[latest.outcome] : "Belum direkam"}</Badge>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.55fr_1fr]">
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Hasil komunikasi
          <select aria-label="Hasil komunikasi" value={outcome} onChange={(event) => setOutcome(event.target.value as Outcome)} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">
            {COMMUNICATION_OUTCOMES.map((value) => <option key={value} value={value}>{labels[value]}</option>)}
          </select>
        </label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Catatan operator opsional
          <textarea aria-label="Catatan operator opsional" value={note} maxLength={2000} onChange={(event) => setNote(event.target.value)} className="mt-2 min-h-20 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" onClick={submit} disabled={!operatorReady || !operatorToken || submitting || hydrating} className="h-9 rounded-md bg-slate-950 px-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
          {submitting ? "Merekam..." : "Rekam Communication Outcome"}
        </button>
        <span role="status" className={`text-xs ${status?.tone === "error" ? "text-red-600" : "text-slate-500"}`}>
          {!operatorReady ? "Token operator diperlukan" : hydrating ? "Memuat communication outcome terbaru..." : status?.text ?? (latest ? "Communication outcome terbaru dimuat." : "Belum ada communication outcome")}
        </span>
      </div>

      {latest && operatorReady && !hydrating ? (
        <div className="mt-5 rounded-md border border-emerald-200 bg-emerald-50 p-4" aria-label="Communication outcome terbaru">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-emerald-700">Outcome umum terbaru</p>
          <p className="mt-2 text-sm font-semibold text-slate-950">{labels[latest.outcome]}</p>
          {latest.note ? <p className="mt-2 text-sm leading-6 text-slate-700">{latest.note}</p> : null}
          <p className="mt-2 text-xs text-slate-500">Direkam oleh {latest.actor} pada {new Date(latest.recordedAt).toLocaleString("id-ID")}</p>
        </div>
      ) : null}
    </Card>
  );
}
