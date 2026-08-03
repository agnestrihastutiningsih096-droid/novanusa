import { executeCommunicationOutcomeCommand } from "@/lib/communication-outcome-command";
import { appendCommunicationOutcome, getCommunicationOutcomeCommand } from "@/lib/communication-outcome-store";
import { getOperatorActor } from "@/lib/email-sender";
import { findProspectById } from "@/lib/institution-data";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeCommunicationOutcomeCommand(request, id, {
    getOperatorActor,
    institutionExists: (institutionId) => Boolean(findProspectById(institutionId)),
    procurementIdentityBelongsToInstitution: () => false,
    getCommand: getCommunicationOutcomeCommand,
    append: appendCommunicationOutcome,
  });
}
