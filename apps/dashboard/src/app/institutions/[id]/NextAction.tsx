"use client";

import { useEffect, useState } from "react";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import type { WorkflowState, WorkflowStatePatch } from "@/lib/workflow-state-types";

type NextActionProps = {
  institutionId: string;
};

const actionOptions = ["Call Again", "Send Catalog", "Send Quotation", "Waiting Response", "Schedule Meeting", "Other"];

async function postWorkflowState(institutionId: string, patch: WorkflowStatePatch) {
  const response = await fetch(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });

  if (!response.ok) {
    throw new Error("Failed to save workflow state");
  }

  return (await response.json()) as WorkflowState;
}

export default function NextAction({ institutionId }: NextActionProps) {
  const [action, setAction] = useState(actionOptions[0]);
  const [note, setNote] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [message, setMessage] = useState("Load pending");

  useEffect(() => {
    let active = true;

    fetch(`/api/institutions/${encodeURIComponent(institutionId)}/workflow-state`)
      .then((response) => response.json() as Promise<WorkflowState>)
      .then((state) => {
        if (!active) return;
        setAction(state.nextAction.action || actionOptions[0]);
        setNote(state.nextAction.note);
        setSavedAt(state.nextAction.savedAt);
        setMessage(state.nextAction.savedAt ? "Loaded saved action" : "No saved action yet");
      })
      .catch(() => {
        if (active) setMessage("Could not load action");
      });

    return () => {
      active = false;
    };
  }, [institutionId]);

  async function saveAction() {
    const saved = new Date().toISOString();
    const state = await postWorkflowState(institutionId, { nextAction: { action, note, savedAt: saved } });
    setAction(state.nextAction.action);
    setNote(state.nextAction.note);
    setSavedAt(state.nextAction.savedAt);
    setMessage("Saved to backend");
  }

  async function clearAction() {
    const state = await postWorkflowState(institutionId, { nextAction: { action: actionOptions[0], note: "", savedAt: null } });
    setAction(state.nextAction.action);
    setNote(state.nextAction.note);
    setSavedAt(null);
    setMessage("Cleared and saved to backend");
  }

  return (
    <Card className="p-5 md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Next Action</p>
          <h2 className="mt-2 text-base font-semibold text-slate-950">Plan the next sales step</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">Set the next backend-persisted action for this institution. No reminders are sent yet.</p>
        </div>
        <Badge tone={savedAt ? "success" : "info"}>{savedAt ? "Action saved" : action}</Badge>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[0.45fr_1fr]">
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Action<select value={action} onChange={(event) => { setAction(event.target.value); setSavedAt(null); setMessage("Edited. Save action to persist."); }} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800">{actionOptions.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
        <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Optional note<input value={note} onChange={(event) => { setNote(event.target.value); setSavedAt(null); setMessage("Edited. Save action to persist."); }} className="mt-2 h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100" /></label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button type="button" onClick={saveAction} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Save Next Action</button>
        <button type="button" onClick={clearAction} className="h-9 rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Clear Action</button>
        <span className="text-xs text-slate-500">{savedAt ? `Last saved ${new Date(savedAt).toLocaleString("id-ID")}` : message}</span>
      </div>
    </Card>
  );
}
