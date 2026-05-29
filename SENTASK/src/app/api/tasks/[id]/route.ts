import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { removeTaskCalendarEvent, syncTaskToGoogleCalendar } from "@/lib/google/calendar";
import { prisma } from "@/lib/prisma";
import { notifyTaskAssigned, notifyTaskUpdated } from "@/lib/services/notifications";
import { scheduleNextRecurringTask } from "@/lib/services/recurring";
import { canAccessTask, canManageTasks } from "@/lib/access";
import { getGoogleWorkspaceSettings } from "@/lib/settings";
import { z } from "zod";
import { CalendarSyncStatus } from "@prisma/client";

async function withCoAssignees<T extends { coAssigneeIds: string[] }>(task: T) {
  if (!task.coAssigneeIds.length) return { ...task, coAssignees: [] };
  const users = await prisma.user.findMany({
    where: { id: { in: task.coAssigneeIds } },
    select: { id: true, name: true, email: true, avatarUrl: true },
  });
  const map = Object.fromEntries(users.map((u) => [u.id, u]));
  return { ...task, coAssignees: task.coAssigneeIds.map((id) => map[id]).filter(Boolean) };
}

const updateTaskSchema = z.object({
  title: z.string().min(1).max(255).optional(),
  customTitle: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  status: z.enum(["BACKLOG", "TODO", "IN_PROGRESS", "WAITING", "DONE"]).optional(),
  priority: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"]).optional(),
  repeatType: z.enum(["NONE", "DAILY", "WEEKLY", "MONTHLY"]).optional(),
  dueDate: z.string().optional().nullable(),
  startDate: z.string().optional().nullable(),
  reminderAt: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
  assigneeId: z.string().optional().nullable(),
  departmentId: z.string().optional().nullable(),
  templateId: z.string().optional().nullable(),
  notifyEmail: z.boolean().optional(),
  notifyTelegram: z.boolean().optional(),
  notifyEmailAddress: z.string().email().optional().nullable(),
  emailRecipients: z.array(z.string().email()).optional(),
  createCalendarEvent: z.boolean().optional(),
  googleCalendarId: z.string().optional().nullable(),
  isArchived: z.boolean().optional(),
  tags: z.array(z.string().max(50)).max(10).optional(),
  estimatedMinutes: z.number().int().min(0).optional().nullable(),
  coAssigneeIds: z.array(z.string()).optional(),
});

const TASK_INCLUDE = {
  assignee: { select: { id: true, name: true, email: true, avatarUrl: true, jobTitle: true, telegramChatId: true, telegramUsername: true, notifyByEmail: true, notifyByTelegram: true } },
  creator: { select: { id: true, name: true, email: true, avatarUrl: true } },
  department: true,
  template: true,
  comments: {
    include: { author: { select: { id: true, name: true, email: true, avatarUrl: true } } },
    orderBy: { createdAt: "asc" as const },
    take: 50,
  },
  attachments: true,
  activityLogs: {
    include: { user: { select: { id: true, name: true, avatarUrl: true } } },
    orderBy: { createdAt: "desc" as const },
    take: 20,
  },
  notificationLogs: {
    orderBy: { createdAt: "desc" as const },
    take: 20,
  },
  _count: { select: { comments: true, attachments: true } },
} as const;

async function getDefaultCalendarId() {
  const workspaceSettings = await getGoogleWorkspaceSettings();
  return workspaceSettings.defaultCalendarId === "primary"
    ? null
    : workspaceSettings.defaultCalendarId;
}

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id }, include: TASK_INCLUDE });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return NextResponse.json(await withCoAssignees(task));
}

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = updateTaskSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed", details: parsed.error.flatten() }, { status: 422 });
  }

  const data = parsed.data;
  const updates: any = { ...data };

  if (data.dueDate !== undefined) updates.dueDate = data.dueDate ? new Date(data.dueDate) : null;
  if (data.startDate !== undefined) updates.startDate = data.startDate ? new Date(data.startDate) : null;
  if (data.reminderAt !== undefined) updates.reminderAt = data.reminderAt ? new Date(data.reminderAt) : null;
  if (data.googleCalendarId !== undefined) {
    updates.googleCalendarId = data.googleCalendarId || null;
  } else if (data.createCalendarEvent === true && !task.createCalendarEvent && !task.googleCalendarId) {
    updates.googleCalendarId = await getDefaultCalendarId();
  }

  if (data.status === "DONE" && task.status !== "DONE") {
    updates.completedAt = new Date();
    updates.isOverdue = false;
  } else if (data.status && data.status !== "DONE" && task.status === "DONE") {
    updates.completedAt = null;
  }

  if (
    data.createCalendarEvent !== undefined ||
    data.googleCalendarId !== undefined ||
    data.status !== undefined ||
    data.title !== undefined ||
    data.description !== undefined ||
    data.dueDate !== undefined ||
    data.startDate !== undefined ||
    data.reminderAt !== undefined ||
    data.repeatType !== undefined ||
    data.assigneeId !== undefined
  ) {
    updates.calendarSyncStatus = updates.createCalendarEvent === false
      ? CalendarSyncStatus.NONE
      : CalendarSyncStatus.OUTDATED;
    updates.calendarSyncError = null;
  }

  // Track changes for activity log
  const changes: Record<string, { from: any; to: any }> = {};
  const trackFields = ["status", "priority", "assigneeId", "dueDate", "title", "createCalendarEvent", "googleCalendarId"] as const;
  for (const field of trackFields) {
    if (data[field] !== undefined && String(data[field]) !== String((task as any)[field])) {
      changes[field] = { from: (task as any)[field], to: data[field] };
    }
  }

  const updated = await prisma.task.update({ where: { id: params.id }, data: updates, include: TASK_INCLUDE });

  // Activity log — single createMany instead of N sequential inserts
  if (Object.keys(changes).length > 0) {
    await prisma.activityLog.createMany({
      data: Object.entries(changes).map(([field, { from, to }]) => ({
        action: `task.${field}_changed`,
        field,
        oldValue: String(from),
        newValue: String(to),
        userId: session.user.id,
        taskId: task.id,
      })),
    });

    // Notify primary assignee
    if (task.assigneeId) {
      await notifyTaskUpdated({
        taskId: task.id,
        updatedById: session.user.id,
        changes,
      });
    }
  }

  // Notify newly added co-assignees
  if (data.coAssigneeIds) {
    const newCoIds = data.coAssigneeIds.filter(
      (id) => !task.coAssigneeIds.includes(id) && id !== session.user.id && id !== updated.assigneeId
    );
    for (const coId of newCoIds) {
      await notifyTaskAssigned({
        taskId: task.id,
        assigneeId: coId,
        assignerName: session.user.name || session.user.email || "SENTASK",
      }).catch(() => {});
    }
  }

  // Schedule next recurring instance when task is completed
  if (data.status === "DONE" && task.status !== "DONE" && updated.repeatType !== "NONE") {
    void scheduleNextRecurringTask({
      id: task.id,
      title: updated.title,
      customTitle: updated.customTitle,
      description: updated.description,
      priority: updated.priority,
      repeatType: updated.repeatType,
      dueDate: updated.dueDate,
      notes: updated.notes,
      assigneeId: updated.assigneeId,
      departmentId: updated.departmentId,
      templateId: updated.templateId,
      creatorId: updated.creatorId,
      notifyEmail: updated.notifyEmail,
      notifyTelegram: updated.notifyTelegram,
      notifyEmailAddress: updated.notifyEmailAddress,
      emailRecipients: updated.emailRecipients,
      createCalendarEvent: updated.createCalendarEvent,
      googleCalendarId: updated.googleCalendarId,
    }).catch((err) => {
      console.error(`[recurring] Failed to schedule next task for ${task.id}:`, err);
    });
  }

  if (!updated.createCalendarEvent && updated.googleCalendarEventId) {
    void removeTaskCalendarEvent(updated.id).catch((error) => {
      console.error(`[calendar-sync:delete-link] Failed to remove task ${updated.id}:`, error);
    });
  } else if (updated.createCalendarEvent) {
    void syncTaskToGoogleCalendar(updated.id).catch((error) => {
      console.error(`[calendar-sync:update] Failed to sync task ${updated.id}:`, error);
    });
  }

  return NextResponse.json(await withCoAssignees(updated));
}

export async function DELETE(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!canManageTasks(session.user)) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  if (task.googleCalendarEventId) {
    await removeTaskCalendarEvent(task.id).catch((error) => {
      console.error(`[calendar-sync:archive] Failed to remove task ${task.id}:`, error);
    });
  }

  await prisma.task.update({ where: { id: params.id }, data: { isArchived: true } });
  await prisma.activityLog.create({
    data: { action: "task.archived", userId: session.user.id, taskId: params.id },
  });

  return NextResponse.json({ success: true });
}
