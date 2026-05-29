/**
 * SENTASK — Overdue Task Checker Cron Job
 *
 * Endpoint: GET /api/cron/overdue
 *
 * Deployment options:
 * - Vercel Cron: add to vercel.json → runs every 6 hours
 * - External cron: use cURL or a cron service to call this endpoint
 * - GitHub Actions: scheduled workflow calling this endpoint
 *
 * Security: Protected by CRON_SECRET header
 *
 * vercel.json example:
 * {
 *   "crons": [{ "path": "/api/cron/overdue", "schedule": "0 * /6 * * *" }]
 * }
 */

import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { notifyTaskOverdue } from "@/lib/services/notifications";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  // Validate cron secret
  const authHeader = req.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const now = new Date();

  try {
    // Find tasks that became overdue and haven't been marked yet
    const overdueTasks = await prisma.task.findMany({
      where: {
        isArchived: false,
        isOverdue: false,
        status: { notIn: ["DONE"] },
        dueDate: { lt: now },
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

    let processed = 0;
    let notified = 0;
    const errors: string[] = [];

    for (const task of overdueTasks) {
      try {
        // Mark as overdue
        await prisma.task.update({
          where: { id: task.id },
          data: { isOverdue: true },
        });

        // Log activity
        await prisma.activityLog.create({
          data: {
            action: "task.became_overdue",
            taskId: task.id,
            details: { dueDate: task.dueDate, markedAt: now },
          },
        });

        // Send notifications
        await notifyTaskOverdue({
          id: task.id,
          title: task.title,
          priority: task.priority,
          dueDate: task.dueDate,
          assigneeId: task.assigneeId,
          notifyEmail: task.notifyEmail,
          notifyTelegram: task.notifyTelegram,
          emailRecipients: task.emailRecipients,
          assignee: task.assignee,
        });

        processed++;
        notified++;
      } catch (err: any) {
        console.error(`Failed to process overdue task ${task.id}:`, err);
        errors.push(`task:${task.id} — ${err.message}`);
        processed++;
      }
    }

    console.log(`[CRON:overdue] Processed ${processed} tasks, notified ${notified}, errors: ${errors.length}`);

    return NextResponse.json({
      success: true,
      processed,
      notified,
      errors: errors.length > 0 ? errors : undefined,
      runAt: now.toISOString(),
    });
  } catch (err: any) {
    console.error("[CRON:overdue] Fatal error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
