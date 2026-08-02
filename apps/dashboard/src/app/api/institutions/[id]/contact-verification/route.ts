import { executeContactVerificationCommand } from "@/lib/contact-verification-command";
import { getContactVerification, saveContactVerification } from "@/lib/contact-verification-store";
import { getOperatorActor } from "@/lib/email-sender";
import { findProspectById } from "@/lib/institution-data";

type RouteContext = { params: Promise<{ id: string }> };

export async function POST(request: Request, context: RouteContext) {
  const { id } = await context.params;
  return executeContactVerificationCommand(request, id, {
    getOperatorActor,
    findProspectById,
    getContactVerification,
    saveContactVerification,
  });
}
