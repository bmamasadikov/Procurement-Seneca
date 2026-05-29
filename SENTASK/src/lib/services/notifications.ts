/**
 * SENTASK — Unified Notification Service
 * Orchestrates in-app, email, Telegram DM, and Telegram group notifications.
 */

import { prisma } from "@/lib/prisma";
import { sendTaskAssignedEmail, sendTaskDueSoonEmail, sendTaskOverdueEmail } from "@/lib/email";
import {
  sendTaskAssignedTelegram,
  sendTaskOverdueTelegram,
  sendTaskDueSoonTelegram,
  sendTaskUpdatedTelegram,
  sendCommentTelegram,
  sendGroupNotification,
} from "@/lib/services/telegram";
import { NotificationChannel, NotificationProvider, NotificationStatus, NotificationType } from "@prisma/client";

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function logNotification(params: {
  channel: NotificationChannel;
  provider?: NotificationProvider;
  type: NotificationType;
  status: NotificationStatus;
  recipient: string;
  subject?: string;
  body: string;
  userId?: string;
  taskId?: string;
  providerMessageId?: string;
  errorMessage?: string;
  sentAt?: Date;
}) {
  try {
    await prisma.notificationLog.create({
      data: {
        ...params,
        provider: params.provider || NotificationProvider.IN_APP,
        sentAt: params.status === NotificationStatus.SENT ? new Date() : undefined,
      },
    });
  } catch (err) {
    console.error("Failed to log notification:", err);
  }
}

async function createInAppNotification(params: {
  type: NotificationType;
  title: string;
  message: string;
  userId: string;
  taskId?: string;
}) {
  return prisma.notification.create({ data: params });
}

async function getGroupChatId(): Promise<string> {
  const row = await prisma.appSetting.findUnique({ where: { key: "telegram.group_chat_id" } });
  return row?.value || process.env.TELEGRAM_GROUP_CHAT_ID || "";
}

async function storeGroupMessage(messageId: number, chatId: string, taskId: string) {
  try {
    await prisma.telegramGroupMessage.upsert({
      where: { messageId },
      update: { taskId, chatId },
      create: { messageId, chatId, taskId },
    });
  } catch (err) {
    console.error("[telegram-group] failed to store message ID:", err);
  }
}

// ─── Task Assigned ────────────────────────────────────────────────────────────

export async function notifyTaskAssigned(params: {
  taskId: string;
  assigneeId: string;
  assignerName: string;
}) {
  const { taskId, assigneeId, assignerName } = params;

  const [task, assignee] = await Promise.all([
    prisma.task.findUnique({
      where: { id: taskId },
      include: { template: true, department: true },
    }),
    prisma.user.findUnique({ where: { id: assigneeId } }),
  ]);

  if (!task || !assignee) return;

  // 1. In-app
  await createInAppNotification({
    type: NotificationType.TASK_ASSIGNED,
    title: "New Task Assigned",
    message: `You have been assigned: "${task.title}"`,
    userId: assigneeId,
    taskId,
  });

  // 2. Email
  if (task.notifyEmail && assignee.notifyByEmail) {
    const recipients = [assignee.email, ...task.emailRecipients].filter(
      (e, i, arr) => e && arr.indexOf(e) === i
    );
    try {
      const result = await sendTaskAssignedEmail({
        to: recipients,
        task,
        assigneeName: assignee.name,
        assignerName,
      });
      await logNotification({
        channel: NotificationChannel.EMAIL,
        provider: result?.provider === "GMAIL_API" ? NotificationProvider.GMAIL_API : NotificationProvider.SMTP,
        type: NotificationType.TASK_ASSIGNED,
        status: NotificationStatus.SENT,
        recipient: recipients.join(", "),
        subject: `[SENTASK] New Task: ${task.title}`,
        body: `Task assigned to ${assignee.name}`,
        userId: assignee.id,
        taskId,
        providerMessageId: result?.providerMessageId,
        sentAt: new Date(),
      });
    } catch (err: any) {
      console.error("Email notification failed:", err);
      await logNotification({
        channel: NotificationChannel.EMAIL,
        provider: NotificationProvider.SMTP,
        type: NotificationType.TASK_ASSIGNED,
        status: NotificationStatus.FAILED,
        recipient: assignee.email,
        body: `Task assigned to ${assignee.name}`,
        userId: assignee.id,
        taskId,
        errorMessage: err.message,
      });
    }
  }

  // 3. Telegram DM
  if (task.notifyTelegram && assignee.notifyByTelegram && assignee.telegramChatId) {
    const result = await sendTaskAssignedTelegram({
      chatId: assignee.telegramChatId,
      taskId,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      assignerName,
      department: task.department?.name,
      template: task.template?.name,
    });
    await logNotification({
      channel: NotificationChannel.TELEGRAM,
      provider: NotificationProvider.TELEGRAM_BOT,
      type: NotificationType.TASK_ASSIGNED,
      status: result.success ? NotificationStatus.SENT : NotificationStatus.FAILED,
      recipient: assignee.telegramChatId,
      body: `Task assigned: ${task.title}`,
      userId: assignee.id,
      taskId,
      sentAt: result.success ? new Date() : undefined,
      errorMessage: result.error,
    });
  } else if (task.notifyTelegram && assignee.notifyByTelegram && !assignee.telegramChatId) {
    await logNotification({
      channel: NotificationChannel.TELEGRAM,
      provider: NotificationProvider.TELEGRAM_BOT,
      type: NotificationType.TASK_ASSIGNED,
      status: NotificationStatus.SKIPPED,
      recipient: "unknown",
      body: `No Telegram chat ID for user ${assignee.email}`,
      userId: assignee.id,
      taskId,
      errorMessage: "User has no telegramChatId configured",
    });
  }

  // 4. Telegram Group
  const groupChatId = await getGroupChatId();
  if (groupChatId) {
    const result = await sendGroupNotification({
      groupChatId,
      taskId,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      assigneeName: assignee.name,
      byName: assignerName,
      department: task.department?.name,
      eventType: "assigned",
    });
    if (result.success && result.messageId) {
      await storeGroupMessage(result.messageId, groupChatId, taskId);
    }
  }
}

// ─── Task Updated ─────────────────────────────────────────────────────────────

export async function notifyTaskUpdated(params: {
  taskId: string;
  updatedById: string;
  changes: Record<string, { from: any; to: any }>;
}) {
  const { taskId, updatedById, changes } = params;
  if (Object.keys(changes).length === 0) return;

  const task = await prisma.task.findUnique({
    where: { id: taskId },
    include: { assignee: true },
  });
  const updatedBy = await prisma.user.findUnique({ where: { id: updatedById } });

  if (!task || !task.assignee || task.assigneeId === updatedById) return;

  const changeLines = Object.entries(changes)
    .map(([k, v]) => `• ${k}: ${v.from} → <b>${v.to}</b>`)
    .join("\n");

  // In-app
  await createInAppNotification({
    type: NotificationType.TASK_UPDATED,
    title: "Task Updated",
    message: `"${task.title}" was updated by ${updatedBy?.name || "someone"}`,
    userId: task.assigneeId!,
    taskId,
  });

  // Telegram DM
  if (task.notifyTelegram && task.assignee.notifyByTelegram && task.assignee.telegramChatId) {
    const result = await sendTaskUpdatedTelegram({
      chatId: task.assignee.telegramChatId,
      taskId,
      taskTitle: task.title,
      changedBy: updatedBy?.name || "Manager",
      changes: changeLines,
    });
    await logNotification({
      channel: NotificationChannel.TELEGRAM,
      provider: NotificationProvider.TELEGRAM_BOT,
      type: NotificationType.TASK_UPDATED,
      status: result.success ? NotificationStatus.SENT : NotificationStatus.FAILED,
      recipient: task.assignee.telegramChatId,
      body: `Task updated: ${task.title}`,
      userId: task.assignee.id,
      taskId,
      sentAt: result.success ? new Date() : undefined,
      errorMessage: result.error,
    });
  }

  // Telegram Group
  const groupChatId = await getGroupChatId();
  if (groupChatId) {
    const result = await sendGroupNotification({
      groupChatId,
      taskId,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      assigneeName: task.assignee.name,
      byName: updatedBy?.name || "Manager",
      eventType: "updated",
      extra: changeLines,
    });
    if (result.success && result.messageId) {
      await storeGroupMessage(result.messageId, groupChatId, taskId);
    }
  }
}

// ─── Task Overdue ─────────────────────────────────────────────────────────────

export async function notifyTaskOverdue(task: {
  id: string;
  title: string;
  priority: string;
  dueDate: Date | null;
  assigneeId: string | null;
  notifyEmail: boolean;
  notifyTelegram: boolean;
  emailRecipients: string[];
  assignee?: { id: string; name: string; email: string; telegramChatId: string | null; notifyByEmail: boolean; notifyByTelegram: boolean } | null;
}) {
  if (!task.assignee) return;

  // In-app
  await createInAppNotification({
    type: NotificationType.TASK_OVERDUE,
    title: "Task Overdue",
    message: `"${task.title}" is overdue and needs your attention`,
    userId: task.assignee.id,
    taskId: task.id,
  });

  // Email
  if (task.notifyEmail && task.assignee.notifyByEmail) {
    try {
      const result = await sendTaskOverdueEmail({
        to: task.assignee.email,
        name: task.assignee.name,
        task: { id: task.id, title: task.title, dueDate: task.dueDate },
      });
      await logNotification({
        channel: NotificationChannel.EMAIL,
        provider: result.provider === "GMAIL_API" ? NotificationProvider.GMAIL_API : NotificationProvider.SMTP,
        type: NotificationType.TASK_OVERDUE,
        status: NotificationStatus.SENT,
        recipient: task.assignee.email,
        subject: `[SENTASK] Overdue: ${task.title}`,
        body: `Task overdue: ${task.title}`,
        userId: task.assignee.id,
        taskId: task.id,
        providerMessageId: result.providerMessageId,
        sentAt: new Date(),
      });
    } catch (err: any) {
      await logNotification({
        channel: NotificationChannel.EMAIL,
        provider: NotificationProvider.SMTP,
        type: NotificationType.TASK_OVERDUE,
        status: NotificationStatus.FAILED,
        recipient: task.assignee.email,
        body: `Task overdue: ${task.title}`,
        userId: task.assignee.id,
        taskId: task.id,
        errorMessage: err.message,
      });
    }
  }

  // Telegram DM
  if (task.notifyTelegram && task.assignee.notifyByTelegram && task.assignee.telegramChatId) {
    const result = await sendTaskOverdueTelegram({
      chatId: task.assignee.telegramChatId,
      taskId: task.id,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
    });
    await logNotification({
      channel: NotificationChannel.TELEGRAM,
      provider: NotificationProvider.TELEGRAM_BOT,
      type: NotificationType.TASK_OVERDUE,
      status: result.success ? NotificationStatus.SENT : NotificationStatus.FAILED,
      recipient: task.assignee.telegramChatId,
      body: `Task overdue: ${task.title}`,
      userId: task.assignee.id,
      taskId: task.id,
      sentAt: result.success ? new Date() : undefined,
      errorMessage: result.error,
    });
  }

  // Telegram Group
  const groupChatId = await getGroupChatId();
  if (groupChatId) {
    const result = await sendGroupNotification({
      groupChatId,
      taskId: task.id,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      assigneeName: task.assignee.name,
      byName: "System",
      eventType: "overdue",
    });
    if (result.success && result.messageId) {
      await storeGroupMessage(result.messageId, groupChatId, task.id);
    }
  }
}

// ─── Comment Added ────────────────────────────────────────────────────────────

export async function notifyCommentAdded(params: {
  taskId: string;
  commenterId: string;
  commentContent: string;
}) {
  const { taskId, commenterId, commentContent } = params;

  const [task, commenter] = await Promise.all([
    prisma.task.findUnique({
      where: { id: taskId },
      include: { assignee: true, creator: true },
    }),
    prisma.user.findUnique({ where: { id: commenterId } }),
  ]);

  if (!task || !commenter) return;

  const notifyUserIds = new Set<string>();
  if (task.creatorId && task.creatorId !== commenterId) notifyUserIds.add(task.creatorId);
  if (task.assigneeId && task.assigneeId !== commenterId) notifyUserIds.add(task.assigneeId);

  for (const userId of notifyUserIds) {
    await createInAppNotification({
      type: NotificationType.COMMENT_ADDED,
      title: "New Comment",
      message: `${commenter.name} commented on "${task.title}"`,
      userId,
      taskId,
    });
  }

  // Telegram DM to assignee
  if (task.assignee && task.assignee.telegramChatId && task.assignee.notifyByTelegram && task.assigneeId !== commenterId) {
    const result = await sendCommentTelegram({
      chatId: task.assignee.telegramChatId,
      taskId,
      taskTitle: task.title,
      commenterName: commenter.name,
      comment: commentContent,
    });
    await logNotification({
      channel: NotificationChannel.TELEGRAM,
      provider: NotificationProvider.TELEGRAM_BOT,
      type: NotificationType.COMMENT_ADDED,
      status: result.success ? NotificationStatus.SENT : NotificationStatus.FAILED,
      recipient: task.assignee.telegramChatId,
      body: `Comment by ${commenter.name}`,
      userId: task.assignee.id,
      taskId,
      sentAt: result.success ? new Date() : undefined,
      errorMessage: result.error,
    });
  }

  // Telegram Group
  const groupChatId = await getGroupChatId();
  if (groupChatId) {
    const preview = commentContent.length > 120 ? commentContent.slice(0, 117) + "..." : commentContent;
    const result = await sendGroupNotification({
      groupChatId,
      taskId,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      assigneeName: task.assignee?.name,
      byName: commenter.name,
      eventType: "comment",
      extra: `<i>${preview}</i>`,
    });
    if (result.success && result.messageId) {
      await storeGroupMessage(result.messageId, groupChatId, taskId);
    }
  }
}

// ─── @Mention ────────────────────────────────────────────────────────────────

export async function notifyMentioned(params: {
  taskId: string;
  commentId: string;
  mentionedUserId: string;
  mentionedByName: string;
  commentContent: string;
}) {
  const { taskId, mentionedUserId, mentionedByName, commentContent } = params;

  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task) return;

  await createInAppNotification({
    type: NotificationType.MENTIONED,
    title: "You were mentioned",
    message: `${mentionedByName} mentioned you in "${task.title}": "${commentContent.slice(0, 80)}${commentContent.length > 80 ? "…" : ""}"`,
    userId: mentionedUserId,
    taskId,
  });
}

export async function notifyTaskDueSoon(params: {
  taskId: string;
  assigneeId: string;
  hoursUntilDue: number;
}) {
  const { taskId, assigneeId, hoursUntilDue } = params;
  const [task, assignee] = await Promise.all([
    prisma.task.findUnique({
      where: { id: taskId },
      include: { template: true },
    }),
    prisma.user.findUnique({ where: { id: assigneeId } }),
  ]);

  if (!task || !assignee || !task.notifyEmail || !assignee.notifyByEmail) return;

  const result = await sendTaskDueSoonEmail({
    to: assignee.email,
    name: assignee.name,
    task: {
      id: task.id,
      title: task.title,
      dueDate: task.dueDate,
      template: task.template,
      priority: task.priority,
    },
    hoursUntilDue,
  });

  await logNotification({
    channel: NotificationChannel.EMAIL,
    provider: result.provider === "GMAIL_API" ? NotificationProvider.GMAIL_API : NotificationProvider.SMTP,
    type: NotificationType.TASK_DUE_SOON,
    status: NotificationStatus.SENT,
    recipient: assignee.email,
    subject: `[SENTASK] Due Soon: ${task.title}`,
    body: `Task due soon: ${task.title}`,
    userId: assignee.id,
    taskId: task.id,
    providerMessageId: result.providerMessageId,
    sentAt: new Date(),
  });

  // Telegram DM for due soon
  if (task.notifyTelegram && assignee.notifyByTelegram && assignee.telegramChatId) {
    await sendTaskDueSoonTelegram({
      chatId: assignee.telegramChatId,
      taskId,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      hoursUntilDue,
    });
  }

  // Telegram Group for due soon
  const groupChatId = await getGroupChatId();
  if (groupChatId) {
    const timeStr = hoursUntilDue <= 1 ? "less than 1 hour" : `${Math.round(hoursUntilDue)} hours`;
    const result2 = await sendGroupNotification({
      groupChatId,
      taskId,
      taskTitle: task.title,
      priority: task.priority,
      dueDate: task.dueDate,
      assigneeName: assignee.name,
      byName: "System",
      eventType: "assigned",
      extra: `⏰ Due in <b>${timeStr}</b>`,
    });
    if (result2.success && result2.messageId) {
      await storeGroupMessage(result2.messageId, groupChatId, taskId);
    }
  }
}
