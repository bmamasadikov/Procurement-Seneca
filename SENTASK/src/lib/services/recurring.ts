import { prisma } from "@/lib/prisma";
import { CalendarSyncStatus, Priority, RepeatType } from "@prisma/client";
import { notifyTaskAssigned } from "@/lib/services/notifications";

type RecurringSource = {
  id: string;
  title: string;
  customTitle: string | null;
  description: string | null;
  priority: Priority;
  repeatType: RepeatType;
  dueDate: Date | null;
  notes: string | null;
  assigneeId: string | null;
  departmentId: string | null;
  templateId: string | null;
  creatorId: string;
  notifyEmail: boolean;
  notifyTelegram: boolean;
  notifyEmailAddress: string | null;
  emailRecipients: string[];
  createCalendarEvent: boolean;
  googleCalendarId: string | null;
};

function getNextDueDate(current: Date | null, repeatType: RepeatType): Date {
  const base = current ? new Date(current) : new Date();
  if (repeatType === RepeatType.DAILY) base.setDate(base.getDate() + 1);
  else if (repeatType === RepeatType.WEEKLY) base.setDate(base.getDate() + 7);
  else if (repeatType === RepeatType.MONTHLY) base.setMonth(base.getMonth() + 1);
  return base;
}

export async function scheduleNextRecurringTask(source: RecurringSource): Promise<void> {
  if (source.repeatType === RepeatType.NONE) return;

  const dueDate = getNextDueDate(source.dueDate, source.repeatType);

  const nextTask = await prisma.task.create({
    data: {
      title: source.title,
      customTitle: source.customTitle,
      description: source.description,
      priority: source.priority,
      repeatType: source.repeatType,
      dueDate,
      notes: source.notes,
      assigneeId: source.assigneeId,
      departmentId: source.departmentId,
      templateId: source.templateId,
      creatorId: source.creatorId,
      notifyEmail: source.notifyEmail,
      notifyTelegram: source.notifyTelegram,
      notifyEmailAddress: source.notifyEmailAddress,
      emailRecipients: source.emailRecipients,
      createCalendarEvent: source.createCalendarEvent,
      googleCalendarId: source.googleCalendarId,
      calendarSyncStatus: source.createCalendarEvent
        ? CalendarSyncStatus.OUTDATED
        : CalendarSyncStatus.NONE,
      parentTaskId: source.id,
      status: "TODO",
    },
  });

  await prisma.activityLog.create({
    data: {
      action: "task.recurring_created",
      taskId: nextTask.id,
      details: {
        parentTaskId: source.id,
        repeatType: source.repeatType,
        dueDate: dueDate.toISOString(),
      },
    },
  });

  if (nextTask.assigneeId) {
    void notifyTaskAssigned({
      taskId: nextTask.id,
      assigneeId: nextTask.assigneeId,
      assignerName: "SENTASK (recurring)",
    }).catch((err) => {
      console.error(`[recurring] Notify failed for task ${nextTask.id}:`, err);
    });
  }
}
