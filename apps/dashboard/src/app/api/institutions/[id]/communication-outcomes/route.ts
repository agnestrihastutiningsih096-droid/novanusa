import { executeCommunicationOutcomeCommand, executeCommunicationOutcomeRead } from "@/lib/communication-outcome-command";
import { appendCommunicationOutcome, getCommunicationOutcomeCommand, getLatestGenericCommunicationOutcome } from "@/lib/communication-outcome-store";
import { getOperatorActor } from "@/lib/email-sender";
import { findProspectById } from "@/lib/institution-data";

type RouteContext = { params: Promise<{ id: string }> };

export async function GET(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeCommunicationOutcomeRead(request, id, {
    getOperatorActor,
    institutionExists: (institutionId) => Boolean(findProspectById(institutionId)),
    getLatestGeneric: getLatestGenericCommunicationOutcome,
  });
}

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
