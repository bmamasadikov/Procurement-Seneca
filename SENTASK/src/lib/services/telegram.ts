/**
 * SENTASK — Telegram Notification Service
 * Supports individual DMs and a shared group chat with inline action buttons.
 *
 * Environment variables:
 *   TELEGRAM_BOT_TOKEN      — from @BotFather
 *   TELEGRAM_DEV_MODE=true  — log instead of send (auto-enabled when no token)
 *   APP_URL                 — public URL for task links
 *
 * Group chat settings are stored in AppSetting (key: telegram.group_chat_id / telegram.webhook_secret).
 */

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || "";
const DEV_MODE = !BOT_TOKEN || process.env.TELEGRAM_DEV_MODE === "true";
const APP_URL = process.env.APP_URL || "http://localhost:3000";
const TELEGRAM_API = `https://api.telegram.org/bot${BOT_TOKEN}`;

export interface TelegramMessageResult {
  success: boolean;
  messageId?: number;
  error?: string;
}

const PRIORITY_EMOJI: Record<string, string> = {
  CRITICAL: "🔴",
  HIGH: "🟠",
  MEDIUM: "🔵",
  LOW: "⚪",
};

// ─── Low-level helpers ────────────────────────────────────────────────────────

async function apiCall(method: string, payload: object): Promise<{ ok: boolean; result?: any; description?: string }> {
  if (DEV_MODE) {
    console.log(`[TELEGRAM DEV] ${method}:`, JSON.stringify(payload, null, 2));
    return { ok: true, result: { message_id: Math.floor(Math.random() * 100000) } };
  }
  try {
    const res = await fetch(`${TELEGRAM_API}/${method}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.json();
  } catch (err: any) {
    return { ok: false, description: err.message };
  }
}

async function sendMessage(chatId: string, text: string, extra?: object): Promise<TelegramMessageResult> {
  const data = await apiCall("sendMessage", {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
    ...extra,
  });
  if (!data.ok) return { success: false, error: data.description };
  return { success: true, messageId: data.result?.message_id };
}

export async function answerCallbackQuery(callbackQueryId: string, text: string, showAlert = false) {
  await apiCall("answerCallbackQuery", {
    callback_query_id: callbackQueryId,
    text,
    show_alert: showAlert,
  });
}

export async function editMessageText(chatId: string, messageId: number, text: string, removeKeyboard = false) {
  await apiCall("editMessageText", {
    chat_id: chatId,
    message_id: messageId,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: true,
    ...(removeKeyboard ? { reply_markup: { inline_keyboard: [] } } : {}),
  });
}

export async function setWebhook(url: string, secretToken: string): Promise<{ ok: boolean; description?: string }> {
  return apiCall("setWebhook", { url, secret_token: secretToken, allowed_updates: ["message", "callback_query"] });
}

export async function deleteWebhook(): Promise<{ ok: boolean }> {
  return apiCall("deleteWebhook", {});
}

export async function getWebhookInfo(): Promise<{ ok: boolean; result?: any }> {
  return apiCall("getWebhookInfo", {});
}

// ─── Task action keyboard ─────────────────────────────────────────────────────

function taskKeyboard(taskId: string) {
  return {
    inline_keyboard: [
      [
        { text: "✅ Mark Done", callback_data: `done:${taskId}` },
        { text: "💬 Comment", callback_data: `comment:${taskId}` },
      ],
    ],
  };
}

// ─── Individual DM notifications ─────────────────────────────────────────────

export async function sendTaskAssignedTelegram(params: {
  chatId: string;
  taskId: string;
  taskTitle: string;
  priority: string;
  dueDate?: Date | string | null;
  assignerName: string;
  department?: string | null;
  template?: string | null;
}): Promise<TelegramMessageResult> {
  const { chatId, taskId, taskTitle, priority, dueDate, assignerName, department, template } = params;
  const taskUrl = `${APP_URL}/tasks/${taskId}`;
  const pEmoji = PRIORITY_EMOJI[priority] || "⚪";
  const dueDateStr = dueDate
    ? new Date(dueDate).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
    : "No due date";

  const text = `
📋 <b>New Task Assigned — SENTASK</b>

<b>${taskTitle}</b>${template && template !== "Custom" ? `\n<i>Template: ${template}</i>` : ""}

${pEmoji} Priority: <b>${priority}</b>
📅 Due: <b>${dueDateStr}</b>
👤 Assigned by: ${assignerName}${department ? `\n🏢 Department: ${department}` : ""}

<a href="${taskUrl}">→ Open Task</a>`.trim();

  return sendMessage(chatId, text, { reply_markup: taskKeyboard(taskId) });
}

export async function sendTaskOverdueTelegram(params: {
  chatId: string;
  taskId: string;
  taskTitle: string;
  priority: string;
  dueDate?: Date | string | null;
}): Promise<TelegramMessageResult> {
  const { chatId, taskId, taskTitle, priority, dueDate } = params;
  const taskUrl = `${APP_URL}/tasks/${taskId}`;
  const pEmoji = PRIORITY_EMOJI[priority] || "⚪";
  const dueDateStr = dueDate ? new Date(dueDate).toLocaleDateString("en-GB") : "N/A";

  const text = `
⚠️ <b>Overdue Task — SENTASK</b>

Task <b>"${taskTitle}"</b> is overdue!

${pEmoji} Priority: <b>${priority}</b>
📅 Was due: <b>${dueDateStr}</b>

<a href="${taskUrl}">→ View Task</a>`.trim();

  return sendMessage(chatId, text, { reply_markup: taskKeyboard(taskId) });
}

export async function sendTaskDueSoonTelegram(params: {
  chatId: string;
  taskId: string;
  taskTitle: string;
  priority: string;
  dueDate?: Date | string | null;
  hoursUntilDue: number;
}): Promise<TelegramMessageResult> {
  const { chatId, taskId, taskTitle, priority, dueDate, hoursUntilDue } = params;
  const taskUrl = `${APP_URL}/tasks/${taskId}`;
  const pEmoji = PRIORITY_EMOJI[priority] || "⚪";
  const timeStr = hoursUntilDue <= 1 ? "less than 1 hour" : `${Math.round(hoursUntilDue)} hours`;

  const text = `
⏰ <b>Task Due Soon — SENTASK</b>

<b>"${taskTitle}"</b> is due in <b>${timeStr}</b>

${pEmoji} Priority: <b>${priority}</b>
📅 Due: <b>${dueDate ? new Date(dueDate).toLocaleDateString("en-GB") : "N/A"}</b>

<a href="${taskUrl}">→ Open Task</a>`.trim();

  return sendMessage(chatId, text, { reply_markup: taskKeyboard(taskId) });
}

export async function sendTaskUpdatedTelegram(params: {
  chatId: string;
  taskId: string;
  taskTitle: string;
  changedBy: string;
  changes: string;
}): Promise<TelegramMessageResult> {
  const { chatId, taskId, taskTitle, changedBy, changes } = params;
  const taskUrl = `${APP_URL}/tasks/${taskId}`;

  const text = `
🔄 <b>Task Updated — SENTASK</b>

<b>"${taskTitle}"</b> was updated by ${changedBy}

${changes}

<a href="${taskUrl}">→ View Task</a>`.trim();

  return sendMessage(chatId, text, { reply_markup: taskKeyboard(taskId) });
}

export async function sendCommentTelegram(params: {
  chatId: string;
  taskId: string;
  taskTitle: string;
  commenterName: string;
  comment: string;
}): Promise<TelegramMessageResult> {
  const { chatId, taskId, taskTitle, commenterName, comment } = params;
  const taskUrl = `${APP_URL}/tasks/${taskId}`;
  const preview = comment.length > 100 ? comment.slice(0, 97) + "..." : comment;

  const text = `
💬 <b>New Comment — SENTASK</b>

Task: <b>"${taskTitle}"</b>
By: ${commenterName}

<i>${preview}</i>

<a href="${taskUrl}">→ View Comment</a>`.trim();

  return sendMessage(chatId, text);
}

// ─── Group chat notifications ─────────────────────────────────────────────────

export async function sendGroupNotification(params: {
  groupChatId: string;
  taskId: string;
  taskTitle: string;
  priority: string;
  dueDate?: Date | string | null;
  assigneeName?: string | null;
  byName: string;
  department?: string | null;
  eventType: "assigned" | "updated" | "overdue" | "done" | "comment";
  extra?: string;
}): Promise<TelegramMessageResult> {
  const { groupChatId, taskId, taskTitle, priority, dueDate, assigneeName, byName, department, eventType, extra } = params;
  const taskUrl = `${APP_URL}/tasks/${taskId}`;
  const pEmoji = PRIORITY_EMOJI[priority] || "⚪";
  const dueDateStr = dueDate
    ? new Date(dueDate).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" })
    : "No due date";

  const headers: Record<string, string> = {
    assigned: "📋 New Task Assigned",
    updated: "🔄 Task Updated",
    overdue: "⚠️ Overdue Task",
    done: "✅ Task Completed",
    comment: "💬 New Comment",
  };

  const lines: string[] = [
    `<b>${headers[eventType] || "📋 Task Update"} — SENTASK</b>`,
    "",
    `<b>${taskTitle}</b>`,
    "",
    `${pEmoji} Priority: <b>${priority}</b>`,
    `📅 Due: <b>${dueDateStr}</b>`,
  ];
  if (assigneeName) lines.push(`👤 Assignee: ${assigneeName}`);
  lines.push(`👤 By: ${byName}`);
  if (department) lines.push(`🏢 Department: ${department}`);
  if (extra) lines.push(`\n${extra}`);
  lines.push("", `<a href="${taskUrl}">→ Open Task</a>`);

  const showKeyboard = eventType !== "done";
  return sendMessage(groupChatId, lines.join("\n"), showKeyboard ? { reply_markup: taskKeyboard(taskId) } : undefined);
}
