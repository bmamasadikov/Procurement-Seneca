import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { auth } from "@/lib/auth";
import { getGoogleWorkspaceSettings, updateGoogleWorkspaceSettings } from "@/lib/settings";

const updateGoogleWorkspaceSettingsSchema = z.object({
  allowedDomains: z.array(z.string().min(1)).optional(),
  autoProvisionUsers: z.boolean().optional(),
  adminApprovalRequired: z.boolean().optional(),
  calendarSyncEnabled: z.boolean().optional(),
  defaultCreateCalendarEvents: z.boolean().optional(),
  defaultCalendarId: z.string().min(1).optional(),
  calendarCompletionBehavior: z.enum(["KEEP", "MARK_DONE", "DELETE"]).optional(),
  reminderMinutesBefore: z.number().int().min(5).max(10080).optional(),
  gmailSendingMode: z.enum(["SMTP", "GMAIL_API"]).optional(),
  defaultSenderEmail: z.string().email().optional(),
  directorySyncEnabled: z.boolean().optional(),
  driveAttachmentsEnabled: z.boolean().optional(),
});

async function requireSession() {
  const session = await auth();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  return session;
}

async function requireAdmin() {
  const session = await requireSession();
  if (session instanceof NextResponse) return session;

  if (session.user.role !== "ADMIN") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return session;
}

export async function GET() {
  const session = await requireSession();
  if (session instanceof NextResponse) return session;

  const settings = await getGoogleWorkspaceSettings();
  return NextResponse.json(settings);
}

export async function PATCH(req: NextRequest) {
  const session = await requireAdmin();
  if (session instanceof NextResponse) return session;

  const body = await req.json();
  const parsed = updateGoogleWorkspaceSettingsSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten() },
      { status: 422 }
    );
  }

  const settings = await updateGoogleWorkspaceSettings(parsed.data);
  return NextResponse.json(settings);
}
