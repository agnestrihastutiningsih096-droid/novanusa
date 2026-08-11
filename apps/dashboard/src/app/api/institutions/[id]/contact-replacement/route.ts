import { executeContactReplacementCommand } from "@/lib/contact-override-command";
import { appendContactOverrideEvent, getContactOverrideEvents } from "@/lib/contact-override-store";
import { getOperatorActor } from "@/lib/email-sender";
import { findProspectById } from "@/lib/institution-data";
type RouteContext = { params: Promise<{ id: string }> };
export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeContactReplacementCommand(request, id, { getOperatorActor, findProspectById, getEvents: getContactOverrideEvents, appendEvent: appendContactOverrideEvent });
}
