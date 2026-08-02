import { NextResponse } from "next/server";
import { getWorkflowState, saveWorkflowState } from "@/lib/workflow-state-store";
import { applyDraftTransition, type WorkflowStatePatch } from "@/lib/workflow-state-types";
import { getOperatorActor } from "@/lib/email-sender";

type RouteContext = {
  params: Promise<{ id: string }>;
};

function unauthorized() {
  return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
}

export async function GET(request: Request, context: RouteContext) {
  if (!getOperatorActor(request)) return unauthorized();
  const { id } = await context.params;
  return NextResponse.json(getWorkflowState(id));
}

export async function POST(request: Request, context: RouteContext) {
  const actor = getOperatorActor(request);
  if (!actor) return unauthorized();
  const { id } = await context.params;
  const patch = (await request.json()) as WorkflowStatePatch;
  if (patch.emailSend || patch.timeline || patch.salesNotes || patch.nextAction) {
    return NextResponse.json({ error: "Only draft workflow transitions are accepted by this endpoint." }, { status: 400 });
  }
  const current = getWorkflowState(id);
  const transition = applyDraftTransition(current.draft, patch.draft ?? {}, actor, new Date().toISOString());
  if (!transition.ok) return NextResponse.json({ error: transition.code }, { status: 409 });
  const state = saveWorkflowState(id, { draft: transition.draft });

  return NextResponse.json(state);
}
