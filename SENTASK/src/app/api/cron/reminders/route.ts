/**
 * SENTASK — Reminder Cron Job
 *
 * Endpoint: GET /api/cron/reminders
 * Schedule: every 30 minutes (Vercel) or hourly
 *
 * Sends reminders for:
 * 1. Tasks with reminderAt <= now that haven't been reminded
 * 2. Tasks due within 24 hours (configurable)
 */

import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { notifyTaskDueSoon } from "@/lib/services/notifications";
import { sendTaskDueSoonTelegram } from "@/lib/services/telegram";
import { NotificationChannel, NotificationProvider, NotificationStatus, NotificationType } from "@prisma/client";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;
  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const now = new Date();
  const in24h = new Date(now.getTime() + 24 * 60 * 60 * 1000);

  try {
    // Find tasks with reminderAt that has passed
    const tasksWithReminder = await prisma.task.findMany({
      where: {
        isArchived: false,
        isOverdue: false,
        status: { notIn: ["DONE"] },
        reminderAt: { lte: now },
        dueDate: { gte: now }, // not yet overdue
        assigneeId: { not: null },
      },
      include: {
        assignee: {
          select: {
            id: true, name: true, email: true,
            telegramChatId: true, notifyByEmail: true, notifyByTelegram: true,
          },
        },
      },
    });

    // Also find tasks due within 24h that haven't been reminded
    const tasksDueSoon = await prisma.task.findMany({
      where: {
        isArchived: false,
        isOverdue: false,
        status: { notIn: ["DONE"] },
        reminderAt: null, // no specific reminder set
        dueDate: { gte: now, lte: in24h },
        assigneeId: { not: null },
      },
      include: {
        assignee: {
          select: {
            id: true, name: true, email: true,
            telegramChatId: true, notifyByEmail: true, notifyByTelegram: true,
          },
        },
      },
    });

    const allTasks = [...tasksWithReminder, ...tasksDueSoon];
    let sent = 0;

    for (const task of allTasks) {
      if (!task.assignee) continue;

      // In-app notification
      const existing = await prisma.notification.findFirst({
        where: {
          taskId: task.id,
          userId: task.assigneeId!,
          type: NotificationType.TASK_DUE_SOON,
          createdAt: { gte: new Date(now.getTime() - 24 * 60 * 60 * 1000) },
        },
      });

      if (!existing) {
        const hoursUntilDue = task.dueDate
          ? (new Date(task.dueDate).getTime() - now.getTime()) / (1000 * 60 * 60)
          : 24;

        await prisma.notification.create({
          data: {
            type: NotificationType.TASK_DUE_SOON,
            title: "Task Due Soon",
            message: `"${task.title}" is due in ${Math.round(hoursUntilDue)} hours`,
            userId: task.assigneeId!,
            taskId: task.id,
          },
        });

        // Telegram reminder
        if (task.notifyEmail && task.assignee.notifyByEmail) {
          try {
            await notifyTaskDueSoon({
              taskId: task.id,
              assigneeId: task.assignee.id,
              hoursUntilDue,
            });
          } catch (error: any) {
            await prisma.notificationLog.create({
              data: {
                channel: NotificationChannel.EMAIL,
                provider: NotificationProvider.SMTP,
                type: NotificationType.TASK_DUE_SOON,
                status: NotificationStatus.FAILED,
                recipient: task.assignee.email,
                body: `Reminder: ${task.title}`,
                userId: task.assignee.id,
                taskId: task.id,
                errorMessage: error.message,
              },
            });
          }
        }

        if (task.notifyTelegram && task.assignee.notifyByTelegram && task.assignee.telegramChatId) {
          const result = await sendTaskDueSoonTelegram({
            chatId: task.assignee.telegramChatId,
            taskId: task.id,
            taskTitle: task.title,
            priority: task.priority,
            dueDate: task.dueDate,
            hoursUntilDue,
          });
          await prisma.notificationLog.create({
            data: {
              channel: NotificationChannel.TELEGRAM,
              provider: NotificationProvider.TELEGRAM_BOT,
              type: NotificationType.TASK_DUE_SOON,
              status: result.success ? NotificationStatus.SENT : NotificationStatus.FAILED,
              recipient: task.assignee.telegramChatId,
              body: `Reminder: ${task.title}`,
              userId: task.assignee.id,
              taskId: task.id,
              sentAt: result.success ? new Date() : undefined,
              errorMessage: result.error,
            },
          });
        }

        // Clear reminderAt after sending
        if (task.reminderAt) {
          await prisma.task.update({
            where: { id: task.id },
            data: { reminderAt: null },
          });
        }

        sent++;
      }
    }

    return NextResponse.json({
      success: true,
      tasksChecked: allTasks.length,
      remindersSent: sent,
      runAt: now.toISOString(),
    });
  } catch (err: any) {
    console.error("[CRON:reminders] Fatal error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
