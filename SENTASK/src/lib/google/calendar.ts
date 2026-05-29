import { google } from "googleapis";
import { addDays, differenceInMinutes, format } from "date-fns";
import { CalendarSyncStatus, RepeatType, TaskStatus } from "@prisma/client";
import { prisma } from "@/lib/prisma";
import { getGoogleWorkspaceDelegatedAdminEmail, getDelegatedGoogleAuth, GOOGLE_WORKSPACE_SCOPES } from "@/lib/google/workspace";
import { getGoogleWorkspaceSettings } from "@/lib/settings";

const TASK_CALENDAR_INCLUDE = {
  assignee: {
    select: {
      id: true,
      name: true,
      email: true,
      googleEmail: true,
      googleCalendarId: true,
    },
  },
  creator: {
    select: {
      id: true,
      name: true,
      email: true,
    },
  },
  template: {
    select: {
      id: true,
      name: true,
    },
  },
} as const;

type CalendarTask = NonNullable<Awaited<ReturnType<typeof loadTaskForCalendar>>>;

function getRepeatRule(repeatType: RepeatType) {
  switch (repeatType) {
    case "DAILY":
      return "RRULE:FREQ=DAILY";
    case "WEEKLY":
      return "RRULE:FREQ=WEEKLY";
    case "MONTHLY":
      return "RRULE:FREQ=MONTHLY";
    default:
      return null;
  }
}

function buildTaskUrl(taskId: string) {
  const appUrl = process.env.APP_URL || "http://localhost:3000";
  return `${appUrl}/tasks/${taskId}`;
}

function buildTaskEventDescription(task: CalendarTask) {
  const taskUrl = buildTaskUrl(task.id);

  return [
    task.description ? `Description: ${task.description}` : null,
    `Priority: ${task.priority}`,
    `Status: ${task.status}`,
    `Assignee: ${task.assignee?.name || "Unassigned"}`,
    `Assigned By: ${task.creator.name}`,
    task.template?.name ? `Template: ${task.template.name}` : null,
    task.dueDate ? `Due Date: ${format(task.dueDate, "PPP")}` : null,
    `Task Link: ${taskUrl}`,
  ]
    .filter(Boolean)
    .join("\n");
}

function buildEventDateRange(task: CalendarTask) {
  const start = task.startDate || task.dueDate;
  if (!start) return null;

  const normalizedStart = new Date(start);
  const normalizedEndBase = task.dueDate || task.startDate || start;
  const normalizedEnd = addDays(new Date(normalizedEndBase), 1);

  return {
    start: { date: format(normalizedStart, "yyyy-MM-dd") },
    end: { date: format(normalizedEnd, "yyyy-MM-dd") },
  };
}

function buildReminderOverrides(task: CalendarTask, defaultMinutes: number) {
  if (!task.dueDate) {
    return [{ method: "popup" as const, minutes: defaultMinutes }];
  }

  if (!task.reminderAt) {
    return [
      { method: "popup" as const, minutes: defaultMinutes },
      { method: "email" as const, minutes: defaultMinutes },
    ];
  }

  const minutes = Math.max(5, differenceInMinutes(task.dueDate, task.reminderAt));
  return [
    { method: "popup" as const, minutes },
    { method: "email" as const, minutes },
  ];
}

async function loadTaskForCalendar(taskId: string) {
  return prisma.task.findUnique({
    where: { id: taskId },
    include: TASK_CALENDAR_INCLUDE,
  });
}

async function clearCalendarLink(taskId: string) {
  await prisma.task.update({
    where: { id: taskId },
    data: {
      googleCalendarEventId: null,
      googleCalendarHtmlLink: null,
      calendarSyncStatus: CalendarSyncStatus.NONE,
      calendarSyncError: null,
      calendarLastSyncedAt: new Date(),
    },
  });
}

function getCalendarTarget(task: CalendarTask) {
  const delegatedAdmin = getGoogleWorkspaceDelegatedAdminEmail();
  const subject =
    task.assignee?.googleEmail ||
    task.assignee?.email ||
    process.env.GOOGLE_WORKSPACE_CALENDAR_IMPERSONATION_EMAIL ||
    delegatedAdmin;

  if (!subject) {
    throw new Error(
      "No Google Workspace subject available for Calendar impersonation. Set GOOGLE_WORKSPACE_CALENDAR_IMPERSONATION_EMAIL or GOOGLE_WORKSPACE_DELEGATED_ADMIN_EMAIL."
    );
  }

  const calendarId =
    task.googleCalendarId ||
    task.assignee?.googleCalendarId ||
    task.assignee?.googleEmail ||
    task.assignee?.email ||
    "primary";

  return { subject, calendarId };
}

export async function syncTaskToGoogleCalendar(taskId: string) {
  const settings = await getGoogleWorkspaceSettings();
  const task = await loadTaskForCalendar(taskId);

  if (!task) throw new Error("Task not found");

  if (!settings.calendarSyncEnabled) {
    await prisma.task.update({
      where: { id: taskId },
      data: {
        calendarSyncStatus: CalendarSyncStatus.NONE,
        calendarSyncError: "Calendar sync is disabled in settings.",
      },
    });
    return { skipped: true };
  }

  if (!task.createCalendarEvent) {
    if (task.googleCalendarEventId) {
      await removeTaskCalendarEvent(taskId);
    } else {
      await clearCalendarLink(taskId);
    }
    return { skipped: true };
  }

  if (!task.dueDate && !task.startDate) {
    await prisma.task.update({
      where: { id: taskId },
      data: {
        calendarSyncStatus: CalendarSyncStatus.FAILED,
        calendarSyncError: "Task needs a due date or start date before creating a Google Calendar event.",
      },
    });
    return { skipped: true };
  }

  const { subject, calendarId } = getCalendarTarget(task);
  const auth = await getDelegatedGoogleAuth({
    subject,
    scopes: [GOOGLE_WORKSPACE_SCOPES.calendar],
  });
  const calendar = google.calendar({ version: "v3", auth });

  if (task.isArchived || (task.status === TaskStatus.DONE && settings.calendarCompletionBehavior === "DELETE")) {
    await removeTaskCalendarEvent(taskId, { calendarId, subject });
    return { removed: true };
  }

  const eventDateRange = buildEventDateRange(task);
  if (!eventDateRange) {
    throw new Error("Unable to build Google Calendar event date range.");
  }

  const recurrenceRule = getRepeatRule(task.repeatType);
  const summaryPrefix =
    task.status === TaskStatus.DONE && settings.calendarCompletionBehavior === "MARK_DONE"
      ? "[Done] "
      : "";

  const requestBody = {
    summary: `${summaryPrefix}${task.title}`,
    description: buildTaskEventDescription(task),
    ...eventDateRange,
    reminders: {
      useDefault: false,
      overrides: buildReminderOverrides(task, settings.reminderMinutesBefore),
    },
    recurrence: recurrenceRule ? [recurrenceRule] : undefined,
  };

  try {
    const response = task.googleCalendarEventId
      ? await calendar.events.update({
          calendarId,
          eventId: task.googleCalendarEventId,
          requestBody,
        })
      : await calendar.events.insert({
          calendarId,
          requestBody,
        });

    await prisma.task.update({
      where: { id: task.id },
      data: {
        googleCalendarEventId: response.data.id || null,
        googleCalendarId: calendarId,
        googleCalendarHtmlLink: response.data.htmlLink || null,
        calendarSyncStatus: CalendarSyncStatus.SYNCED,
        calendarSyncError: null,
        calendarLastSyncedAt: new Date(),
      },
    });

    return {
      synced: true,
      eventId: response.data.id || undefined,
      htmlLink: response.data.htmlLink || undefined,
    };
  } catch (error: any) {
    await prisma.task.update({
      where: { id: task.id },
      data: {
        calendarSyncStatus: CalendarSyncStatus.FAILED,
        calendarSyncError: error.message,
      },
    });
    throw error;
  }
}

export async function removeTaskCalendarEvent(
  taskId: string,
  existingTarget?: { calendarId: string; subject: string }
) {
  const task = await loadTaskForCalendar(taskId);
  if (!task?.googleCalendarEventId) {
    await clearCalendarLink(taskId);
    return { removed: false };
  }

  const target = existingTarget || getCalendarTarget(task);
  const auth = await getDelegatedGoogleAuth({
    subject: target.subject,
    scopes: [GOOGLE_WORKSPACE_SCOPES.calendar],
  });
  const calendar = google.calendar({ version: "v3", auth });

  try {
    await calendar.events.delete({
      calendarId: target.calendarId,
      eventId: task.googleCalendarEventId,
    });
  } catch (error: any) {
    if (error?.code !== 404) {
      await prisma.task.update({
        where: { id: taskId },
        data: {
          calendarSyncStatus: CalendarSyncStatus.FAILED,
          calendarSyncError: error.message,
        },
      });
      throw error;
    }
  }

  await clearCalendarLink(taskId);
  return { removed: true };
}

export async function syncPendingCalendarTasks(limit = 25) {
  const tasks = await prisma.task.findMany({
    where: {
      createCalendarEvent: true,
      isArchived: false,
      OR: [
        { calendarSyncStatus: CalendarSyncStatus.OUTDATED },
        { calendarSyncStatus: CalendarSyncStatus.FAILED },
        { calendarSyncStatus: CalendarSyncStatus.NONE },
        { googleCalendarEventId: null },
      ],
    },
    orderBy: { updatedAt: "asc" },
    take: limit,
  });

  const results: Array<{ taskId: string; status: "SYNCED" | "FAILED"; error?: string }> = [];

  for (const task of tasks) {
    try {
      await syncTaskToGoogleCalendar(task.id);
      results.push({ taskId: task.id, status: "SYNCED" });
    } catch (error: any) {
      results.push({ taskId: task.id, status: "FAILED", error: error.message });
    }
  }

  return results;
}
