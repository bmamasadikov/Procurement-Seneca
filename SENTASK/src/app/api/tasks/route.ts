import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { syncTaskToGoogleCalendar } from "@/lib/google/calendar";
import { notifyTaskAssigned } from "@/lib/services/notifications";
import { canManageTasks, hasFullTaskAccess } from "@/lib/access";
import { getGoogleWorkspaceSettings } from "@/lib/settings";
import { z } from "zod";
import { CalendarSyncStatus, Prisma } from "@prisma/client";

const createTaskSchema = z.object({
  title: z.string().min(1).max(255),
  customTitle: z.string().optional().nullable(),
  description: z.string().optional().nullable(),
  status: z.enum(["BACKLOG", "TODO", "IN_PROGRESS", "WAITING", "DONE"]).default("TODO"),
  priority: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"]).default("MEDIUM"),
  repeatType: z.enum(["NONE", "DAILY", "WEEKLY", "MONTHLY"]).default("NONE"),
  dueDate: z.string().optional().nullable(),
  startDate: z.string().optional().nullable(),
  reminderAt: z.string().optional().nullable(),
  notes: z.string().optional().nullable(),
  assigneeId: z.string().optional().nullable(),
  departmentId: z.string().optional().nullable(),
  templateId: z.string().optional().nullable(),
  notifyEmail: z.boolean().default(true),
  notifyTelegram: z.boolean().default(false),
  notifyEmailAddress: z.string().email().optional().nullable(),
  emailRecipients: z.array(z.string().email()).default([]),
  createCalendarEvent: z.boolean().default(false),
  googleCalendarId: z.string().optional().nullable(),
  tags: z.array(z.string().max(50)).max(10).default([]),
  estimatedMinutes: z.number().int().min(0).optional().nullable(),
  coAssigneeIds: z.array(z.string()).default([]),
});

async function populateCoAssignees<T extends { coAssigneeIds: string[] }>(tasks: T[]) {
  const allIds = [...new Set(tasks.flatMap((t) => t.coAssigneeIds))];
  if (allIds.length === 0) return tasks.map((t) => ({ ...t, coAssignees: [] }));
  const users = await prisma.user.findMany({
    where: { id: { in: allIds } },
    select: { id: true, name: true, email: true, avatarUrl: true },
  });
  const map = Object.fromEntries(users.map((u) => [u.id, u]));
  return tasks.map((t) => ({ ...t, coAssignees: t.coAssigneeIds.map((id) => map[id]).filter(Boolean) }));
}

const TASK_INCLUDE = {
  assignee: { select: { id: true, name: true, email: true, avatarUrl: true, jobTitle: true, telegramChatId: true, telegramUsername: true } },
  creator: { select: { id: true, name: true, email: true, avatarUrl: true } },
  department: true,
  template: true,
  _count: { select: { comments: true, attachments: true } },
} as const;

async function getDefaultCalendarId() {
  const workspaceSettings = await getGoogleWorkspaceSettings();
  return workspaceSettings.defaultCalendarId === "primary"
    ? null
    : workspaceSettings.defaultCalendarId;
}

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const page = Math.max(1, parseInt(searchParams.get("page") || "1"));
  const pageSize = Math.min(100, Math.max(1, parseInt(searchParams.get("pageSize") || "20")));
  const search = searchParams.get("search") || "";
  const status = searchParams.get("status") || "";
  const priority = searchParams.get("priority") || "";
  const assigneeId = searchParams.get("assigneeId") || "";
  const departmentId = searchParams.get("departmentId") || "";
  const repeatType = searchParams.get("repeatType") || "";
  const dueDateFrom = searchParams.get("dueDateFrom") || "";
  const dueDateTo = searchParams.get("dueDateTo") || "";
  const myTasks = searchParams.get("myTasks") === "true";
  const overdueOnly = searchParams.get("overdue") === "true";
  const dueTodayOnly = searchParams.get("dueToday") === "true";
  const templateId = searchParams.get("templateId") || "";
  const tag = searchParams.get("tag") || "";

  const filters: Prisma.TaskWhereInput[] = [{ isArchived: false }];

  if (!hasFullTaskAccess(session.user) || myTasks) {
    filters.push({
      OR: [
        { assigneeId: session.user.id },
        { creatorId: session.user.id },
      ],
    });
  }

  if (search) {
    filters.push({
      OR: [
      { title: { contains: search, mode: "insensitive" } },
      { description: { contains: search, mode: "insensitive" } },
      { customTitle: { contains: search, mode: "insensitive" } },
      ],
    });
  }

  if (!overdueOnly && status) filters.push({ status: status as any });
  if (priority) filters.push({ priority: priority as any });
  if (assigneeId) filters.push({ assigneeId });
  if (departmentId) filters.push({ departmentId });
  if (repeatType) filters.push({ repeatType: repeatType as any });
  if (templateId) filters.push({ templateId });
  if (tag) filters.push({ tags: { has: tag } });

  if (dueTodayOnly) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    filters.push({ dueDate: { gte: today, lt: tomorrow } });
  } else if (dueDateFrom || dueDateTo) {
    const dueDate: NonNullable<Prisma.TaskWhereInput["dueDate"]> = {};
    if (dueDateFrom) dueDate.gte = new Date(dueDateFrom);
    if (dueDateTo) dueDate.lte = new Date(dueDateTo);
    filters.push({ dueDate });
  }

  if (overdueOnly) {
    filters.push({
      isOverdue: true,
      status: { notIn: ["DONE"] },
    });
  }

  const where: Prisma.TaskWhereInput =
    filters.length === 1 ? filters[0] : { AND: filters };

  const [tasks, total] = await Promise.all([
    prisma.task.findMany({
      where,
      include: TASK_INCLUDE,
      orderBy: [
        { isOverdue: "desc" },
        { priority: "asc" },
        { dueDate: { sort: "asc", nulls: "last" } },
        { createdAt: "desc" },
      ],
      skip: (page - 1) * pageSize,
      take: pageSize,
    }),
    prisma.task.count({ where }),
  ]);

  const tasksWithCoAssignees = await populateCoAssignees(tasks);
  return NextResponse.json({ data: tasksWithCoAssignees, total, page, pageSize, totalPages: Math.ceil(total / pageSize) });
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!canManageTasks(session.user)) {
    return NextResponse.json({ error: "Forbidden: only task managers can create tasks" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = createTaskSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed", details: parsed.error.flatten() }, { status: 422 });
  }

  const data = parsed.data;
  const googleCalendarId = data.createCalendarEvent
    ? data.googleCalendarId === undefined
      ? await getDefaultCalendarId()
      : data.googleCalendarId || null
    : null;

  const task = await prisma.task.create({
    data: {
      title: data.title,
      customTitle: data.customTitle,
      description: data.description,
      status: data.status,
      priority: data.priority,
      repeatType: data.repeatType,
      dueDate: data.dueDate ? new Date(data.dueDate) : null,
      startDate: data.startDate ? new Date(data.startDate) : null,
      reminderAt: data.reminderAt ? new Date(data.reminderAt) : null,
      notes: data.notes,
      creatorId: session.user.id,
      assigneeId: data.assigneeId || null,
      departmentId: data.departmentId || null,
      templateId: data.templateId || null,
      notifyEmail: data.notifyEmail,
      notifyTelegram: data.notifyTelegram,
      notifyEmailAddress: data.notifyEmailAddress || null,
      emailRecipients: data.emailRecipients,
      createCalendarEvent: data.createCalendarEvent,
      googleCalendarId,
      tags: data.tags,
      estimatedMinutes: data.estimatedMinutes ?? null,
      coAssigneeIds: data.coAssigneeIds,
      calendarSyncStatus: data.createCalendarEvent
        ? CalendarSyncStatus.OUTDATED
        : CalendarSyncStatus.NONE,
    },
    include: { ...TASK_INCLUDE, assignee: { select: { id: true, name: true, email: true, avatarUrl: true } } },
  });

  // Activity log
  await prisma.activityLog.create({
    data: {
      action: "task.created",
      userId: session.user.id,
      taskId: task.id,
      details: { title: task.title, status: task.status, priority: task.priority },
    },
  });

  // Notify primary assignee
  if (task.assigneeId && task.assigneeId !== session.user.id) {
    await notifyTaskAssigned({
      taskId: task.id,
      assigneeId: task.assigneeId,
      assignerName: session.user.name || session.user.email || "SENTASK",
    });
  }
  // Notify co-assignees
  for (const coId of data.coAssigneeIds) {
    if (coId !== session.user.id && coId !== task.assigneeId) {
      await notifyTaskAssigned({
        taskId: task.id,
        assigneeId: coId,
        assignerName: session.user.name || session.user.email || "SENTASK",
      }).catch(() => {});
    }
  }

  if (task.createCalendarEvent) {
    void syncTaskToGoogleCalendar(task.id).catch((error) => {
      console.error(`[calendar-sync:create] Failed to sync task ${task.id}:`, error);
    });
  }

  return NextResponse.json(task, { status: 201 });
}
