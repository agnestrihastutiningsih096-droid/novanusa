import fs from "fs";
import path from "path";
import { createDefaultWorkflowState, type WorkflowState, type WorkflowStatePatch } from "@/lib/workflow-state-types";

const workflowStatePath = path.resolve(process.cwd(), "..", "..", "data", "dashboard_workflow_state.json");

type WorkflowStateFile = Record<string, WorkflowState>;

function ensureStoreDirectory() {
  fs.mkdirSync(path.dirname(workflowStatePath), { recursive: true });
}

function normalizeState(value: Partial<WorkflowState> | undefined): WorkflowState {
  const defaults = createDefaultWorkflowState();

  return {
    draft: { ...defaults.draft, ...(value?.draft ?? {}) },
    salesNotes: { ...defaults.salesNotes, ...(value?.salesNotes ?? {}) },
    nextAction: { ...defaults.nextAction, ...(value?.nextAction ?? {}) },
    timeline: { ...defaults.timeline, ...(value?.timeline ?? {}) },
    emailSend: { ...defaults.emailSend, ...(value?.emailSend ?? {}) },
  };
}

function readStore(): WorkflowStateFile {
  ensureStoreDirectory();

  if (!fs.existsSync(workflowStatePath)) {
    return {};
  }

  try {
    const parsed = JSON.parse(fs.readFileSync(workflowStatePath, "utf8")) as WorkflowStateFile;
    return Object.fromEntries(Object.entries(parsed).map(([id, state]) => [id, normalizeState(state)]));
  } catch {
    return {};
  }
}

function writeStore(store: WorkflowStateFile) {
  ensureStoreDirectory();
  const tempPath = `${workflowStatePath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(store, null, 2), "utf8");
  fs.renameSync(tempPath, workflowStatePath);
}

export function getWorkflowStatePath() {
  return workflowStatePath;
}

export function getWorkflowState(institutionId: string): WorkflowState {
  return normalizeState(readStore()[institutionId]);
}

export function getAllWorkflowStates(): WorkflowStateFile {
  return readStore();
}

export function saveWorkflowState(institutionId: string, patch: WorkflowStatePatch): WorkflowState {
  const store = readStore();
  const current = normalizeState(store[institutionId]);
  const next: WorkflowState = {
    draft: { ...current.draft, ...(patch.draft ?? {}) },
    salesNotes: { ...current.salesNotes, ...(patch.salesNotes ?? {}) },
    nextAction: { ...current.nextAction, ...(patch.nextAction ?? {}) },
    timeline: { ...current.timeline, ...(patch.timeline ?? {}) },
    emailSend: { ...current.emailSend, ...(patch.emailSend ?? {}) },
  };

  store[institutionId] = next;
  writeStore(store);
  return next;
}

