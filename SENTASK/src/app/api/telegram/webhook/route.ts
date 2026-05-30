import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { answerCallbackQuery, editMessageText } from "@/lib/services/telegram";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const APP_URL = process.env.APP_URL || "";

async function sendBotMessage(chatId: number | string, text: string) {
  if (!BOT_TOKEN) return;
  await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "HTML" }),
  });
}

const WEBHOOK_SECRET = process.env.TELEGRAM_WEBHOOK_SECRET || "";

export async function POST(req: NextRequest) {
  // Validate secret token sent by Telegram in the X-Telegram-Bot-Api-Secret-Token header
  if (WEBHOOK_SECRET) {
    const incomingSecret = req.headers.get("x-telegram-bot-api-secret-token") || "";
    if (incomingSecret !== WEBHOOK_SECRET) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
  }

  let update: any;
  try {
    update = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  // Handle button clicks (Mark Done / Comment reminder)
  if (update.callback_query) {
    await handleCallbackQuery(update.callback_query);
    return NextResponse.json({ ok: true });
  }

  // Handle /start and /connect commands for account linking
  if (update.message?.text?.startsWith("/")) {
    await handleCommand(update.message);
    return NextResponse.json({ ok: true });
  }

  // Handle text replies to group notification messages
  if (update.message?.reply_to_message && update.message.text) {
    await handleReply(update.message);
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ ok: true });
}

async function handleCommand(message: any) {
  const chatId: number = message.chat?.id;
  const text: string = message.text?.trim() || "";
  const firstName: string = message.from?.first_name || "there";

  // /start or /start <email>
  if (text === "/start" || text.startsWith("/start ")) {
    const email = text.slice(6).trim().toLowerCase();

    if (!email) {
      await sendBotMessage(
        chatId,
        `👋 Hi <b>${firstName}</b>! I'm the <b>SENTASK</b> bot.\n\nTo link your account and receive task notifications, send:\n\n<code>/start your@email.com</code>\n\nUse the email you log in to SENTASK with.`
      );
      return;
    }

    const user = await prisma.user.findUnique({ where: { email } });

    if (!user || !user.isActive) {
      await sendBotMessage(
        chatId,
        `❌ No active SENTASK account found for <b>${email}</b>.\n\nMake sure you use the exact email you log in with, or contact your admin.`
      );
      return;
    }

    // Save the Telegram chat ID to the user record
    await prisma.user.update({
      where: { id: user.id },
      data: {
        telegramChatId: String(chatId),
        telegramUsername: message.from?.username || null,
        notifyByTelegram: true,
      },
    });

    await sendBotMessage(
      chatId,
      `✅ <b>Account linked!</b>\n\nHi ${user.name}, your Telegram is now connected to SENTASK.\n\nYou'll receive notifications here for:\n• New tasks assigned to you\n• Task updates\n• Overdue reminders\n\n<a href="${APP_URL}">→ Open SENTASK</a>`
    );
    return;
  }

  // /disconnect
  if (text === "/disconnect") {
    const existingUser = await prisma.user.findFirst({ where: { telegramChatId: String(chatId) } });
    if (!existingUser) {
      await sendBotMessage(chatId, `ℹ️ Your Telegram isn't linked to any SENTASK account.`);
      return;
    }
    await prisma.user.update({
      where: { id: existingUser.id },
      data: { telegramChatId: null, telegramUsername: null, notifyByTelegram: false },
    });
    await sendBotMessage(chatId, `✅ Disconnected. You'll no longer receive SENTASK notifications here.`);
    return;
  }

  // /whoami
  if (text === "/whoami") {
    const existingUser = await prisma.user.findFirst({ where: { telegramChatId: String(chatId) } });
    if (!existingUser) {
      await sendBotMessage(chatId, `ℹ️ Not linked. Send <code>/start your@email.com</code> to connect.`);
    } else {
      await sendBotMessage(chatId, `✅ Linked as <b>${existingUser.name}</b> (${existingUser.email})`);
    }
    return;
  }
}

async function handleCallbackQuery(cbq: any) {
  const { id: callbackId, data, from, message } = cbq;
  if (!data) return;

  if (data.startsWith("done:")) {
    const taskId = data.slice(5);
    const senderName = from?.first_name || from?.username || "Someone";

    try {
      const task = await prisma.task.findUnique({ where: { id: taskId } });
      if (!task) {
        await answerCallbackQuery(callbackId, "Task not found.", true);
        return;
      }
      if (task.status === "DONE") {
        await answerCallbackQuery(callbackId, "Task is already marked as done.", true);
        return;
      }

      await prisma.task.update({
        where: { id: taskId },
        data: { status: "DONE", completedAt: new Date(), isOverdue: false },
      });

      await prisma.activityLog.create({
        data: {
          action: "task.status_changed",
          field: "status",
          oldValue: task.status,
          newValue: "DONE",
          taskId,
          details: { via: "telegram_group", by: senderName },
        },
      });

      await answerCallbackQuery(callbackId, `✅ "${task.title}" marked as done!`);

      // Edit the original group message to reflect completion
      if (message?.chat?.id && message?.message_id) {
        const chatId = String(message.chat.id);
        await editMessageText(
          chatId,
          message.message_id,
          `✅ <b>Task Completed — SENTASK</b>\n\n<b>${task.title}</b>\n\n<s>Marked done by ${senderName} via Telegram</s>`,
          true
        );
      }
    } catch (err) {
      console.error("[telegram-webhook] failed to mark done:", err);
      await answerCallbackQuery(callbackId, "Failed to update task.", true);
    }

  } else if (data.startsWith("comment:")) {
    await answerCallbackQuery(
      callbackId,
      "Reply to this message in the chat to add a comment.",
      true
    );
  }
}

async function handleReply(message: any) {
  const replyToMessageId: number = message.reply_to_message?.message_id;
  const text: string = message.text?.trim();
  const from = message.from;
  const chatId = String(message.chat?.id || "");

  if (!replyToMessageId || !text || !chatId) return;

  // Look up which task this message was the notification for
  const groupMsg = await prisma.telegramGroupMessage.findUnique({
    where: { messageId: replyToMessageId },
  });
  if (!groupMsg) return;

  const senderName = [from?.first_name, from?.last_name].filter(Boolean).join(" ") || from?.username || "Telegram User";

  // Find or create a system user to attribute the comment to (use task creator as fallback)
  const task = await prisma.task.findUnique({
    where: { id: groupMsg.taskId },
    select: { id: true, title: true, creatorId: true },
  });
  if (!task) return;

  // Create the comment attributed to the task creator (Telegram has no SENTASK account)
  await prisma.taskComment.create({
    data: {
      content: `[via Telegram by ${senderName}]\n${text}`,
      taskId: task.id,
      authorId: task.creatorId,
    },
  });

  await prisma.activityLog.create({
    data: {
      action: "comment.added",
      taskId: task.id,
      userId: task.creatorId,
      details: { via: "telegram_group", by: senderName },
    },
  });
}
