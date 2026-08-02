"use client";

import { useEffect, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { fetchWorkflowStateIfActive } from "@/lib/operator-auth";
import { sendSalesNotesCommandIfActive } from "@/lib/sales-notes-client";
import type { SalesNotesCommandRequest, SalesNotesCommandResponse } from "@/lib/sales-notes-contract";
import type { WorkflowState } from "@/lib/workflow-state-types";
import { useInstitutionOperator } from "./InstitutionOperatorContext";

type SalesNotesState = {
  contactPerson: string;
  conversationNotes: string;
  customerInterest: string;
  requestedDocuments: string;
  internalNotes: string;
};

type SalesNotesProps = {
  institutionId: string;
};

const emptyNotes: SalesNotesState = {
  contactPerson: "",
  conversationNotes: "",
  customerInterest: "",
  requestedDocuments: "",
  internalNotes: "",
};

async function postSalesNotes(institutionId: string, command: SalesNotesCommandRequest, operatorToken: string, operatorReady: boolean) {
  const response = await sendSalesNotesCommandIfActive(institutionId, operatorToken, operatorReady, command);
  if (!response) throw new Error("Token operator diperlukan");
  const payload = (await response.json()) as SalesNotesCommandResponse;
  if (!response.ok || !payload.ok) throw new Error(payload.ok ? "Gagal menyimpan catatan sales" : payload.error.message);
  return payload.salesNotes;
}

export default function SalesNotes({ institutionId }: SalesNotesProps) {
  const { operatorReady, operatorToken } = useInstitutionOperator();
  const [notes, setNotes] = useState<SalesNotesState>(emptyNotes);
  const [savedAt, setTersimpanAt] = useState<string | null>(null);
  const [message, setMessage] = useState("Memuat");

  useEffect(() => {
    if (!operatorReady || !operatorToken) return;
    let active = true;

    fetchWorkflowStateIfActive(institutionId, operatorToken, operatorReady)!
      .then((response) => response.json() as Promise<WorkflowState>)
      .then((state) => {
        if (!active) return;
        setNotes({
          contactPerson: state.salesNotes.contactPerson,
          conversationNotes: state.salesNotes.conversationNotes,
          customerInterest: state.salesNotes.customerInterest,
          requestedDocuments: state.salesNotes.requestedDocuments,
          internalNotes: state.salesNotes.internalNotes,
        });
        setTersimpanAt(state.salesNotes.updatedAt ?? state.salesNotes.savedAt);
        setMessage(state.salesNotes.updatedAt || state.salesNotes.savedAt ? "Catatan tersimpan dimuat" : "Belum ada catatan tersimpan");
      })
      .catch(() => {
        if (active) setMessage("Catatan tidak dapat dimuat");
      });

    return () => {
      active = false;
    };
  }, [institutionId, operatorReady, operatorToken]);

  function updateField(field: keyof SalesNotesState, value: string) {
    setNotes((current) => ({ ...current, [field]: value }));
    setTersimpanAt(null);
    setMessage("Diedit. Simpan catatan agar tersimpan.");
  }

  async function saveNotes() {
    const salesNotes = await postSalesNotes(institutionId, { operation: "update", notes }, operatorToken, operatorReady);
    setNotes({
      contactPerson: salesNotes.contactPerson,
      conversationNotes: salesNotes.conversationNotes,
      customerInterest: salesNotes.customerInterest,
      requestedDocuments: salesNotes.requestedDocuments,
      internalNotes: salesNotes.internalNotes,
    });
    setTersimpanAt(salesNotes.updatedAt);
    setMessage("Tersimpan ke backend");
  }

  async function clearNotes() {
    const salesNotes = await postSalesNotes(institutionId, { operation: "clear" }, operatorToken, operatorReady);
    setNotes({
      contactPerson: salesNotes.contactPerson,
      conversationNotes: salesNotes.conversationNotes,
      customerInterest: salesNotes.customerInterest,
      requestedDocuments: salesNotes.requestedDocuments,
      internalNotes: salesNotes.internalNotes,
    });
    setTersimpanAt(salesNotes.updatedAt);
    setMessage("Dikosongkan dan tersimpan ke backend");
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Catatan Sales</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Konteks sales</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Catat konteks kerja untuk institusi ini. Catatan disimpan pada overlay backend lokal.</p>
        </div>
        <Badge tone={savedAt ? "success" : "neutral"}>{savedAt ? "Tersimpan" : "Belum disimpan"}</Badge>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Narahubung<input value={notes.contactPerson} onChange={(event) => updateField("contactPerson", event.target.value)} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Minat calon pelanggan<input value={notes.customerInterest} onChange={(event) => updateField("customerInterest", event.target.value)} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400 lg:col-span-2">Catatan percakapan<textarea value={notes.conversationNotes} onChange={(event) => updateField("conversationNotes", event.target.value)} className="mt-2 min-h-28 w-full rounded-md border border-slate-200 bg-white p-3 text-sm font-medium normal-case leading-6 tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Dokumen yang diminta<textarea value={notes.requestedDocuments} onChange={(event) => updateField("requestedDocuments", event.target.value)} className="mt-2 min-h-24 w-full rounded-md border border-slate-200 bg-white p-3 text-sm font-medium normal-case leading-6 tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Catatan internal<textarea value={notes.internalNotes} onChange={(event) => updateField("internalNotes", event.target.value)} className="mt-2 min-h-24 w-full rounded-md border border-slate-200 bg-white p-3 text-sm font-medium normal-case leading-6 tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" onClick={saveNotes} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Simpan Catatan</button>
        <button type="button" onClick={clearNotes} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Kosongkan Catatan</button>
        <span className="text-xs text-slate-500">{!operatorReady ? "Token operator diperlukan" : savedAt ? `Terakhir disimpan ${new Date(savedAt).toLocaleString("id-ID")}` : message}</span>
      </div>
    </Card>
  );
}
