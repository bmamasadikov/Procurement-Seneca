import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { setWebhook, deleteWebhook, getWebhookInfo, sendGroupNotification } from "@/lib/services/telegram";

const APP_URL = process.env.APP_URL || "";
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session || session.user.role !== "ADMIN") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const [groupRow, secretRow] = await Promise.all([
    prisma.appSetting.findUnique({ where: { key: "telegram.group_chat_id" } }),
    prisma.appSetting.findUnique({ where: { key: "telegram.webhook_secret" } }),
  ]);

  const webhookInfo = await getWebhookInfo();

  return NextResponse.json({
    botTokenConfigured: !!BOT_TOKEN,
    groupChatId: groupRow?.value || process.env.TELEGRAM_GROUP_CHAT_ID || "",
    webhookSecret: secretRow?.value || process.env.TELEGRAM_WEBHOOK_SECRET || "",
    webhookUrl: `${APP_URL}/api/telegram/webhook`,
    currentWebhook: webhookInfo.result?.url || "",
    webhookPending: webhookInfo.result?.pending_update_count || 0,
  });
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session || session.user.role !== "ADMIN") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const { action, groupChatId, webhookSecret } = body;

  if (action === "save") {
    const ops: Promise<any>[] = [];
    if (groupChatId !== undefined) {
      ops.push(prisma.appSetting.upsert({
        where: { key: "telegram.group_chat_id" },
        update: { value: groupChatId || "" },
        create: { key: "telegram.group_chat_id", value: groupChatId || "" },
      }));
    }
    if (webhookSecret !== undefined) {
      ops.push(prisma.appSetting.upsert({
        where: { key: "telegram.webhook_secret" },
        update: { value: webhookSecret || "" },
        create: { key: "telegram.webhook_secret", value: webhookSecret || "" },
      }));
    }
    await Promise.all(ops);
    return NextResponse.json({ success: true });
  }

  if (action === "setWebhook") {
    if (!BOT_TOKEN) {
      return NextResponse.json({ error: "TELEGRAM_BOT_TOKEN not configured in environment" }, { status: 400 });
    }
    if (!APP_URL) {
      return NextResponse.json({ error: "APP_URL environment variable is not set" }, { status: 400 });
    }
    const secretRow = await prisma.appSetting.findUnique({ where: { key: "telegram.webhook_secret" } });
    const secret = secretRow?.value || process.env.TELEGRAM_WEBHOOK_SECRET || "";
    const webhookUrl = `${APP_URL}/api/telegram/webhook`;
    const result = await setWebhook(webhookUrl, secret);
    if (!result.ok) {
      return NextResponse.json({ error: result.description || "Failed to set webhook" }, { status: 400 });
    }
    return NextResponse.json({ success: true, webhookUrl });
  }

  if (action === "deleteWebhook") {
    const result = await deleteWebhook();
    return NextResponse.json({ success: result.ok });
  }

  if (action === "testMessage") {
    const groupRow = await prisma.appSetting.findUnique({ where: { key: "telegram.group_chat_id" } });
    const gid = groupRow?.value || process.env.TELEGRAM_GROUP_CHAT_ID || "";
    if (!gid) {
      return NextResponse.json({ error: "No group chat ID configured" }, { status: 400 });
    }
    const result = await sendGroupNotification({
      groupChatId: gid,
      taskId: "test",
      taskTitle: "Test Notification",
      priority: "MEDIUM",
      dueDate: new Date(),
      assigneeName: session.user.name || "Admin",
      byName: session.user.name || "Admin",
      eventType: "assigned",
      extra: "This is a test message from SENTASK ✅",
    });
    if (!result.success) {
      return NextResponse.json({ error: result.error || "Failed to send test message" }, { status: 400 });
    }
    return NextResponse.json({ success: true });
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
