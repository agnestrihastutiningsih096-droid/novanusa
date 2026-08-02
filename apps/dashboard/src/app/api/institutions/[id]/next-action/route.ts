import { getOperatorActor } from "@/lib/email-sender";
import { executeNextActionCommand } from "@/lib/next-action-command";
import { saveWorkflowState } from "@/lib/workflow-state-store";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeNextActionCommand(request, id, { getOperatorActor, saveWorkflowState });
}
