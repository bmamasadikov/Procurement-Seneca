import { prisma } from "@/lib/prisma";
import {
  CalendarCompletionBehavior,
  GmailSendingMode,
  GoogleWorkspaceSettings,
} from "@/types";

const GOOGLE_WORKSPACE_SETTINGS_KEYS = {
  allowedDomains: "google_workspace.allowed_domains",
  autoProvisionUsers: "google_workspace.auto_provision_users",
  adminApprovalRequired: "google_workspace.admin_approval_required",
  calendarSyncEnabled: "google_workspace.calendar_sync_enabled",
  defaultCreateCalendarEvents: "google_workspace.default_create_calendar_events",
  defaultCalendarId: "google_workspace.default_calendar_id",
  calendarCompletionBehavior: "google_workspace.calendar_completion_behavior",
  reminderMinutesBefore: "google_workspace.reminder_minutes_before",
  gmailSendingMode: "google_workspace.gmail_sending_mode",
  defaultSenderEmail: "google_workspace.default_sender_email",
  directorySyncEnabled: "google_workspace.directory_sync_enabled",
  driveAttachmentsEnabled: "google_workspace.drive_attachments_enabled",
} as const;

type GoogleWorkspaceSettingsRecord = Omit<
  GoogleWorkspaceSettings,
  "googleClientConfigured" | "googleServiceAccountConfigured"
>;

function parseBoolean(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) return fallback;
  return value === "true";
}

function parseNumber(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseStringArray(value: string | undefined, fallback: string[]): string[] {
  if (!value) return fallback;

  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      return parsed
        .map((item) => String(item).trim().toLowerCase())
        .filter(Boolean);
    }
  } catch {
    return value
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean);
  }

  return fallback;
}

function hasGoogleClientConfig() {
  return Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);
}

function hasGoogleServiceAccountConfig() {
  return Boolean(
    process.env.GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL &&
      process.env.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY
  );
}

const DEFAULT_SHARED_CALENDAR_ID =
  process.env.GOOGLE_WORKSPACE_DEFAULT_CALENDAR_ID ||
  "c_9d7a3ee7e8637ae4e7026b1514ee9e13a127112dab4b464c2761fb81735b2546@group.calendar.google.com";

export const GOOGLE_WORKSPACE_DEFAULTS: GoogleWorkspaceSettingsRecord = {
  allowedDomains: (process.env.GOOGLE_WORKSPACE_ALLOWED_DOMAINS || "seneca.uz")
    .split(",")
    .map((domain) => domain.trim().toLowerCase())
    .filter(Boolean),
  autoProvisionUsers: true,
  adminApprovalRequired: true,
  calendarSyncEnabled: true,
  defaultCreateCalendarEvents: false,
  defaultCalendarId: DEFAULT_SHARED_CALENDAR_ID,
  calendarCompletionBehavior: "MARK_DONE",
  reminderMinutesBefore: 30,
  gmailSendingMode: "GMAIL_API",
  defaultSenderEmail: process.env.GOOGLE_WORKSPACE_DEFAULT_SENDER_EMAIL || "noreply@seneca.uz",
  directorySyncEnabled: true,
  driveAttachmentsEnabled: false,
};

export async function getGoogleWorkspaceSettings(): Promise<GoogleWorkspaceSettings> {
  const rows = await prisma.appSetting.findMany({
    where: {
      key: {
        in: Object.values(GOOGLE_WORKSPACE_SETTINGS_KEYS),
      },
    },
  });

  const settingsMap = new Map(rows.map((row) => [row.key, row.value]));

  const settings: GoogleWorkspaceSettingsRecord = {
    allowedDomains: parseStringArray(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.allowedDomains),
      GOOGLE_WORKSPACE_DEFAULTS.allowedDomains
    ),
    autoProvisionUsers: parseBoolean(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.autoProvisionUsers),
      GOOGLE_WORKSPACE_DEFAULTS.autoProvisionUsers
    ),
    adminApprovalRequired: parseBoolean(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.adminApprovalRequired),
      GOOGLE_WORKSPACE_DEFAULTS.adminApprovalRequired
    ),
    calendarSyncEnabled: parseBoolean(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.calendarSyncEnabled),
      GOOGLE_WORKSPACE_DEFAULTS.calendarSyncEnabled
    ),
    defaultCreateCalendarEvents: parseBoolean(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.defaultCreateCalendarEvents),
      GOOGLE_WORKSPACE_DEFAULTS.defaultCreateCalendarEvents
    ),
    defaultCalendarId:
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.defaultCalendarId) ||
      GOOGLE_WORKSPACE_DEFAULTS.defaultCalendarId,
    calendarCompletionBehavior:
      (settingsMap.get(
        GOOGLE_WORKSPACE_SETTINGS_KEYS.calendarCompletionBehavior
      ) as CalendarCompletionBehavior | undefined) ||
      GOOGLE_WORKSPACE_DEFAULTS.calendarCompletionBehavior,
    reminderMinutesBefore: parseNumber(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.reminderMinutesBefore),
      GOOGLE_WORKSPACE_DEFAULTS.reminderMinutesBefore
    ),
    gmailSendingMode:
      (settingsMap.get(
        GOOGLE_WORKSPACE_SETTINGS_KEYS.gmailSendingMode
      ) as GmailSendingMode | undefined) || GOOGLE_WORKSPACE_DEFAULTS.gmailSendingMode,
    defaultSenderEmail:
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.defaultSenderEmail) ||
      GOOGLE_WORKSPACE_DEFAULTS.defaultSenderEmail,
    directorySyncEnabled: parseBoolean(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.directorySyncEnabled),
      GOOGLE_WORKSPACE_DEFAULTS.directorySyncEnabled
    ),
    driveAttachmentsEnabled: parseBoolean(
      settingsMap.get(GOOGLE_WORKSPACE_SETTINGS_KEYS.driveAttachmentsEnabled),
      GOOGLE_WORKSPACE_DEFAULTS.driveAttachmentsEnabled
    ),
  };

  return {
    ...settings,
    googleClientConfigured: hasGoogleClientConfig(),
    googleServiceAccountConfigured: hasGoogleServiceAccountConfig(),
  };
}

export async function updateGoogleWorkspaceSettings(
  input: Partial<GoogleWorkspaceSettingsRecord>
) {
  const normalized: Partial<GoogleWorkspaceSettingsRecord> = {
    ...input,
    allowedDomains: input.allowedDomains?.map((domain) => domain.trim().toLowerCase()).filter(Boolean),
    defaultSenderEmail: input.defaultSenderEmail?.trim().toLowerCase(),
    defaultCalendarId: input.defaultCalendarId?.trim() || "primary",
  };

  const updates: Array<Promise<unknown>> = [];

  const entries: Array<[keyof GoogleWorkspaceSettingsRecord, string]> = [
    ["allowedDomains", GOOGLE_WORKSPACE_SETTINGS_KEYS.allowedDomains],
    ["autoProvisionUsers", GOOGLE_WORKSPACE_SETTINGS_KEYS.autoProvisionUsers],
    ["adminApprovalRequired", GOOGLE_WORKSPACE_SETTINGS_KEYS.adminApprovalRequired],
    ["calendarSyncEnabled", GOOGLE_WORKSPACE_SETTINGS_KEYS.calendarSyncEnabled],
    ["defaultCreateCalendarEvents", GOOGLE_WORKSPACE_SETTINGS_KEYS.defaultCreateCalendarEvents],
    ["defaultCalendarId", GOOGLE_WORKSPACE_SETTINGS_KEYS.defaultCalendarId],
    ["calendarCompletionBehavior", GOOGLE_WORKSPACE_SETTINGS_KEYS.calendarCompletionBehavior],
    ["reminderMinutesBefore", GOOGLE_WORKSPACE_SETTINGS_KEYS.reminderMinutesBefore],
    ["gmailSendingMode", GOOGLE_WORKSPACE_SETTINGS_KEYS.gmailSendingMode],
    ["defaultSenderEmail", GOOGLE_WORKSPACE_SETTINGS_KEYS.defaultSenderEmail],
    ["directorySyncEnabled", GOOGLE_WORKSPACE_SETTINGS_KEYS.directorySyncEnabled],
    ["driveAttachmentsEnabled", GOOGLE_WORKSPACE_SETTINGS_KEYS.driveAttachmentsEnabled],
  ];

  for (const [field, key] of entries) {
    const value = normalized[field];
    if (value === undefined) continue;

    const storedValue = Array.isArray(value) ? JSON.stringify(value) : String(value);

    updates.push(
      prisma.appSetting.upsert({
        where: { key },
        update: { value: storedValue },
        create: { key, value: storedValue },
      })
    );
  }

  await Promise.all(updates);
  return getGoogleWorkspaceSettings();
}

export async function getAllowedGoogleDomains() {
  const settings = await getGoogleWorkspaceSettings();
  return settings.allowedDomains;
}

export async function isAllowedGoogleDomain(domain: string | null | undefined) {
  if (!domain) return false;
  const normalized = domain.trim().toLowerCase();
  const allowedDomains = await getAllowedGoogleDomains();
  return allowedDomains.includes(normalized);
}

export async function getDefaultSenderEmail() {
  const settings = await getGoogleWorkspaceSettings();
  return settings.defaultSenderEmail;
}
