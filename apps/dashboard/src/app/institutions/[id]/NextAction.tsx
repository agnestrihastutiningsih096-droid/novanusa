"use client";

import { useEffect, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { sendNextActionCommandIfActive } from "@/lib/next-action-client";
import { NEXT_ACTION_VALUES, type NextActionCommandRequest, type NextActionCommandResponse, type NextActionValue } from "@/lib/next-action-contract";
import { fetchWorkflowStateIfActive } from "@/lib/operator-auth";
import type { WorkflowState } from "@/lib/workflow-state-types";
import { useInstitutionOperator } from "./InstitutionOperatorContext";

type NextActionProps = {
  institutionId: string;
};

const actionOptions = NEXT_ACTION_VALUES;

const actionLabels: Record<string, string> = {
  "Call Again": "Telepon Lagi",
  "Send Catalog": "Kirim Katalog",
  "Send Quotation": "Kirim Penawaran",
  "Waiting Response": "Menunggu Respons",
  "Schedule Meeting": "Jadwalkan Meeting",
  Other: "Lainnya",
};

async function postNextAction(institutionId: string, command: NextActionCommandRequest, operatorToken: string, operatorReady: boolean) {
  const response = await sendNextActionCommandIfActive(institutionId, operatorToken, operatorReady, command);
  if (!response) throw new Error("Token operator diperlukan");
  const payload = (await response.json()) as NextActionCommandResponse;
  if (!response.ok || !payload.ok) throw new Error(payload.ok ? "Gagal menyimpan aksi berikutnya" : payload.error.message);
  return payload.nextAction;
}

export default function NextAction({ institutionId }: NextActionProps) {
  const { operatorReady, operatorToken } = useInstitutionOperator();
  const [action, setAction] = useState<NextActionValue>(actionOptions[0]);
  const [note, setNote] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [message, setMessage] = useState("Memuat");

  useEffect(() => {
    if (!operatorReady || !operatorToken) return;
    let active = true;

    fetchWorkflowStateIfActive(institutionId, operatorToken, operatorReady)!
      .then((response) => response.json() as Promise<WorkflowState>)
      .then((state) => {
        if (!active) return;
        setAction(NEXT_ACTION_VALUES.includes(state.nextAction.action as NextActionValue) ? state.nextAction.action as NextActionValue : actionOptions[0]);
        setNote(state.nextAction.note);
        setSavedAt(state.nextAction.savedAt);
        setMessage(state.nextAction.savedAt ? "Aksi tersimpan dimuat" : "Belum ada aksi tersimpan");
      })
      .catch(() => {
        if (active) setMessage("Aksi tidak dapat dimuat");
      });

    return () => {
      active = false;
    };
  }, [institutionId, operatorReady, operatorToken]);

  async function saveAction() {
    const nextAction = await postNextAction(institutionId, { operation: "update", nextAction: { action, note } }, operatorToken, operatorReady);
    setAction(nextAction.action as NextActionValue);
    setNote(nextAction.note);
    setSavedAt(nextAction.savedAt);
    setMessage("Tersimpan ke backend");
  }

  async function clearAction() {
    const nextAction = await postNextAction(institutionId, { operation: "clear" }, operatorToken, operatorReady);
    setAction(nextAction.action as NextActionValue);
    setNote(nextAction.note);
    setSavedAt(nextAction.savedAt);
    setMessage("Dikosongkan dan tersimpan ke backend");
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Aksi Berikutnya</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Rencanakan langkah sales berikutnya</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Tetapkan aksi berikutnya untuk institusi ini dan simpan ke backend. Belum ada pengingat yang dikirim.</p>
        </div>
        <Badge tone={savedAt ? "success" : "info"}>{savedAt ? "Aksi tersimpan" : actionLabels[action] ?? action}</Badge>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.45fr_1fr]">
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Aksi<select value={action} onChange={(event) => { setAction(event.target.value as NextActionValue); setSavedAt(null); setMessage("Diedit. Simpan aksi agar tersimpan."); }} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">{actionOptions.map((option) => <option key={option} value={option}>{actionLabels[option] ?? option}</option>)}</select></label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Catatan opsional<input value={note} onChange={(event) => { setNote(event.target.value); setSavedAt(null); setMessage("Diedit. Simpan aksi agar tersimpan."); }} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" onClick={saveAction} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Simpan Aksi Berikutnya</button>
        <button type="button" onClick={clearAction} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Kosongkan Aksi</button>
        <span className="text-xs text-slate-500">{!operatorReady ? "Token operator diperlukan" : savedAt ? `Terakhir disimpan ${new Date(savedAt).toLocaleString("id-ID")}` : message}</span>
      </div>
    </Card>
  );
}
