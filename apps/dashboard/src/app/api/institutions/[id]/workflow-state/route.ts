import { NextResponse } from "next/server";
import { getWorkflowState, saveWorkflowState } from "@/lib/workflow-state-store";
import type { WorkflowStatePatch } from "@/lib/workflow-state-types";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  return NextResponse.json(getWorkflowState(id));
}

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  const patch = (await request.json()) as WorkflowStatePatch;
  const state = saveWorkflowState(id, patch);

  return NextResponse.json(state);
}
