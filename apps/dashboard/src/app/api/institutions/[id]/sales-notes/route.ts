import { getOperatorActor } from "@/lib/email-sender";
import { executeSalesNotesCommand } from "@/lib/sales-notes-command";
import { saveWorkflowState } from "@/lib/workflow-state-store";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeSalesNotesCommand(request, id, { getOperatorActor, saveWorkflowState });
}
