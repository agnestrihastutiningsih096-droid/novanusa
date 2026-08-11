import fs from "node:fs";
import path from "node:path";
import type { ContactOverrideEvent } from "./contact-override.ts";

const contactOverridePath = process.env.NOVANUSA_CONTACT_OVERRIDES_PATH
  ? path.resolve(process.env.NOVANUSA_CONTACT_OVERRIDES_PATH)
  : path.resolve(process.cwd(), "..", "..", "data", "dashboard_contact_overrides.json");

function readAll(): ContactOverrideEvent[] {
  if (!fs.existsSync(contactOverridePath)) return [];
  try {
    const parsed = JSON.parse(fs.readFileSync(contactOverridePath, "utf8"));
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

export function getContactOverrideEvents(institutionId: string) { return readAll().filter((event) => event.institutionId === institutionId); }
export function appendContactOverrideEvent(event: ContactOverrideEvent) {
  const events = readAll();
  events.push(event);
  fs.mkdirSync(path.dirname(contactOverridePath), { recursive: true });
  const tempPath = `${contactOverridePath}.tmp`;
  fs.writeFileSync(tempPath, JSON.stringify(events, null, 2), "utf8");
  fs.renameSync(tempPath, contactOverridePath);
  return event;
}
export function getContactOverridePath() { return contactOverridePath; }
