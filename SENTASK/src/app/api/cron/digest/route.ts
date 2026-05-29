/**
 * SENTASK — Daily Digest Cron Job
 * Endpoint: POST /api/cron/digest
 * Schedule: daily at 08:00 (add to Vercel cron.json or external cron)
 *
 * Sends each active user a personalized summary:
 *  - Number of overdue tasks
 *  - Tasks due today
 *  - Total open task count
 */

import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { sendDailyDigestEmail } from "@/lib/email";

const CRON_SECRET = process.env.CRON_SECRET;

export async function POST(req: NextRequest) {
  // Validate cron secret if configured
  if (CRON_SECRET) {
    const auth = req.headers.get("authorization");
    if (auth !== `Bearer ${CRON_SECRET}`) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);

  const users = await prisma.user.findMany({
    where: {
      isActive: true,
      notifyByEmail: true,
      role: { not: "PENDING" },
    },
    select: { id: true, name: true, email: true },
  });

  let sent = 0;
  let failed = 0;

  for (const user of users) {
    try {
      const [overdueTasks, dueTodayTasks, totalOpen] = await Promise.all([
        prisma.task.findMany({
          where: {
            assigneeId: user.id,
            isArchived: false,
            isOverdue: true,
            status: { notIn: ["DONE"] },
          },
          select: { id: true, title: true, dueDate: true, priority: true },
          orderBy: { priority: "asc" },
          take: 10,
        }),
        prisma.task.findMany({
          where: {
            assigneeId: user.id,
            isArchived: false,
            status: { notIn: ["DONE"] },
            dueDate: { gte: today, lt: tomorrow },
          },
          select: { id: true, title: true, priority: true },
          orderBy: { priority: "asc" },
          take: 10,
        }),
        prisma.task.count({
          where: {
            assigneeId: user.id,
            isArchived: false,
            status: { notIn: ["DONE"] },
          },
        }),
      ]);

      // Skip users with no tasks at all
      if (totalOpen === 0 && overdueTasks.length === 0 && dueTodayTasks.length === 0) continue;

      await sendDailyDigestEmail({
        to: user.email,
        name: user.name,
        overdue: overdueTasks,
        dueToday: dueTodayTasks,
        totalOpen,
      });

      await prisma.notificationLog.create({
        data: {
          channel: "EMAIL",
          provider: "SMTP",
          type: "TASK_DUE_SOON",
          status: "SENT",
          recipient: user.email,
          subject: `[SENTASK] Daily Digest — ${new Date().toLocaleDateString()}`,
          body: `Daily digest: ${totalOpen} open, ${overdueTasks.length} overdue, ${dueTodayTasks.length} due today`,
          userId: user.id,
          sentAt: new Date(),
        },
      });

      sent++;
    } catch (err) {
      console.error(`[digest] Failed to send to ${user.email}:`, err);
      failed++;
    }
  }

  return NextResponse.json({ sent, failed, total: users.length });
}
