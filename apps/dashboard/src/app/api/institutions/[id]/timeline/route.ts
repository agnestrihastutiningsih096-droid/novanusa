import { getOperatorActor } from "@/lib/email-sender";
import { executeTimelineCommand } from "@/lib/timeline-command";
import { getWorkflowState, saveWorkflowState } from "@/lib/workflow-state-store";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeTimelineCommand(request, id, { getOperatorActor, getWorkflowState, saveWorkflowState });
}
