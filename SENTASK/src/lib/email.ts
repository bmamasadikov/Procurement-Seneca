import { sendWorkspaceEmail, WorkspaceEmailResult } from "@/lib/google/gmail";

const BRAND_COLOR = "#1e3a8a";
const COMPANY = process.env.COMPANY_NAME || "Seneca";
const APP_URL = process.env.APP_URL || "http://localhost:3000";

function priorityBadge(priority: string): string {
  const colors: Record<string, string> = {
    CRITICAL: "#ef4444",
    HIGH: "#f97316",
    MEDIUM: "#3b82f6",
    LOW: "#6b7280",
  };
  const labels: Record<string, string> = {
    CRITICAL: "Critical",
    HIGH: "High",
    MEDIUM: "Medium",
    LOW: "Low",
  };
  return `<span style="background:${colors[priority] || "#6b7280"};color:#fff;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;">${labels[priority] || priority}</span>`;
}

function emailTemplate(content: string): string {
  return `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:32px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr>
          <td style="background:${BRAND_COLOR};padding:24px 32px;">
            <h1 style="margin:0;color:#fff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">
              <span style="background:#fff;color:${BRAND_COLOR};padding:2px 10px;border-radius:6px;font-size:14px;font-weight:800;margin-right:10px;">S</span>
              SENTASK
            </h1>
            <p style="margin:4px 0 0;color:#93c5fd;font-size:13px;">${COMPANY} Internal Task Manager</p>
          </td>
        </tr>
        <!-- Content -->
        <tr>
          <td style="padding:32px;">
            ${content}
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f8faff;padding:16px 32px;border-top:1px solid #e5e7eb;">
            <p style="margin:0;color:#9ca3af;font-size:12px;text-align:center;">
              This is an automated message from SENTASK — ${COMPANY} Internal Task Manager.<br>
              Do not reply to this email.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`;
}

export async function sendVerificationEmail(params: {
  to: string;
  name: string;
  verifyUrl: string;
}) {
  const { to, name, verifyUrl } = params;

  const content = `
    <h2 style="margin:0 0 8px;color:#111827;font-size:20px;">Verify your email address</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">Hi <strong>${name}</strong>, welcome to SENTASK! Click the button below to verify your email and activate your account.</p>
    <div style="text-align:center;margin:24px 0;">
      <a href="${verifyUrl}" style="background:${BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block;">
        Verify Email Address
      </a>
    </div>
    <p style="color:#9ca3af;font-size:13px;text-align:center;">This link expires in 24 hours. After verifying, a Seneca admin will approve your access.</p>
    <p style="color:#9ca3af;font-size:12px;text-align:center;margin-top:12px;">If you didn't create this account, you can safely ignore this email.</p>
  `;

  await sendWorkspaceEmail({
    from: process.env.SMTP_FROM || `SENTASK <noreply@seneca.uz>`,
    to,
    subject: `[SENTASK] Verify your email address`,
    html: emailTemplate(content),
  });
}

export async function sendTaskAssignedEmail(params: {
  to: string[];
  task: { id?: string; title: string; description?: string | null; priority?: string; dueDate?: Date | string | null; template?: { name: string } | null };
  assigneeName: string;
  assignerName: string;
}): Promise<WorkspaceEmailResult | undefined> {
  const { to, task, assigneeName, assignerName } = params;
  if (!to.length) return;

  const taskUrl = `${APP_URL}/tasks/${task.id}`;
  const dueDate = task.dueDate
    ? new Date(task.dueDate).toLocaleDateString("en-GB", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "No due date";

  const content = `
    <h2 style="margin:0 0 8px;color:#111827;font-size:20px;">You have a new task</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">Hi <strong>${assigneeName}</strong>, a task has been assigned to you.</p>

    <div style="background:#f8faff;border:1px solid #e0e7ff;border-radius:10px;padding:20px 24px;margin-bottom:24px;">
      <h3 style="margin:0 0 16px;color:${BRAND_COLOR};font-size:17px;">${task.title}</h3>
      <table cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;width:120px;">Template</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;font-weight:500;">${task.template?.name || "Custom"}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;">Priority</td>
          <td style="padding:6px 0;">${priorityBadge(task.priority || "MEDIUM")}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;">Due Date</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;font-weight:500;">${dueDate}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;">Assigned By</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;font-weight:500;">${assignerName}</td>
        </tr>
        ${task.description ? `<tr><td colspan="2" style="padding-top:12px;color:#374151;font-size:14px;border-top:1px solid #e5e7eb;margin-top:12px;">${task.description}</td></tr>` : ""}
      </table>
    </div>

    <div style="text-align:center;margin:24px 0;">
      <a href="${taskUrl}" style="background:${BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block;">
        Open Task →
      </a>
    </div>
  `;

  return sendWorkspaceEmail({
    from: process.env.SMTP_FROM || `SENTASK <noreply@seneca.uz>`,
    to: to.join(", "),
    subject: `[SENTASK] New Task: ${task.title}`,
    html: emailTemplate(content),
  });
}

export async function sendPasswordResetEmail(params: {
  to: string;
  name: string;
  resetUrl: string;
}) {
  const { to, name, resetUrl } = params;

  const content = `
    <h2 style="margin:0 0 8px;color:#111827;font-size:20px;">Reset Your Password</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">Hi <strong>${name}</strong>, we received a request to reset your SENTASK password.</p>
    <div style="text-align:center;margin:24px 0;">
      <a href="${resetUrl}" style="background:${BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block;">
        Reset Password
      </a>
    </div>
    <p style="color:#9ca3af;font-size:13px;text-align:center;">This link expires in 1 hour. If you didn't request this, ignore this email.</p>
  `;

  await sendWorkspaceEmail({
    from: process.env.SMTP_FROM || `SENTASK <noreply@seneca.uz>`,
    to,
    subject: `[SENTASK] Password Reset Request`,
    html: emailTemplate(content),
  });
}

export async function sendTaskOverdueEmail(params: {
  to: string;
  name: string;
  task: { id?: string; title: string; dueDate?: Date | string | null };
}): Promise<WorkspaceEmailResult> {
  const { to, name, task } = params;

  const content = `
    <h2 style="margin:0 0 8px;color:#ef4444;font-size:20px;">⚠️ Task Overdue</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">Hi <strong>${name}</strong>, the following task is overdue:</p>
    <div style="background:#fff5f5;border:1px solid #fecaca;border-radius:10px;padding:20px 24px;margin-bottom:24px;">
      <h3 style="margin:0 0 8px;color:#dc2626;font-size:17px;">${task.title}</h3>
      <p style="margin:0;color:#6b7280;font-size:13px;">Due: ${task.dueDate ? new Date(task.dueDate).toLocaleDateString() : "N/A"}</p>
    </div>
    <div style="text-align:center;">
      <a href="${APP_URL}/tasks/${task.id}" style="background:#ef4444;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block;">
        View Task
      </a>
    </div>
  `;

  return sendWorkspaceEmail({
    from: process.env.SMTP_FROM || `SENTASK <noreply@seneca.uz>`,
    to,
    subject: `[SENTASK] Overdue Task: ${task.title}`,
    html: emailTemplate(content),
  });
}

export async function sendTaskDueSoonEmail(params: {
  to: string;
  name: string;
  task: { id?: string; title: string; dueDate?: Date | string | null; template?: { name?: string | null } | null; priority?: string | null };
  hoursUntilDue: number;
}): Promise<WorkspaceEmailResult> {
  const { to, name, task, hoursUntilDue } = params;

  const dueDateLabel = task.dueDate
    ? new Date(task.dueDate).toLocaleDateString("en-GB", {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "No due date";

  const content = `
    <h2 style="margin:0 0 8px;color:#111827;font-size:20px;">Task reminder</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">Hi <strong>${name}</strong>, your task is due soon.</p>

    <div style="background:#f8faff;border:1px solid #dbeafe;border-radius:10px;padding:20px 24px;margin-bottom:24px;">
      <h3 style="margin:0 0 16px;color:${BRAND_COLOR};font-size:17px;">${task.title}</h3>
      <table cellpadding="0" cellspacing="0" width="100%">
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;width:120px;">Template</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;font-weight:500;">${task.template?.name || "Custom"}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;">Priority</td>
          <td style="padding:6px 0;">${priorityBadge(task.priority || "MEDIUM")}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;">Due Date</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;font-weight:500;">${dueDateLabel}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:13px;">Time Remaining</td>
          <td style="padding:6px 0;color:#111827;font-size:14px;font-weight:500;">${Math.max(1, Math.round(hoursUntilDue))} hour(s)</td>
        </tr>
      </table>
    </div>

    <div style="text-align:center;">
      <a href="${APP_URL}/tasks/${task.id}" style="background:${BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block;">
        Open Task
      </a>
    </div>
  `;

  return sendWorkspaceEmail({
    from: process.env.SMTP_FROM || `SENTASK <noreply@seneca.uz>`,
    to,
    subject: `[SENTASK] Due Soon: ${task.title}`,
    html: emailTemplate(content),
  });
}

export async function sendDailyDigestEmail(params: {
  to: string;
  name: string;
  overdue: Array<{ id: string; title: string; dueDate: Date | null; priority: string }>;
  dueToday: Array<{ id: string; title: string; priority: string }>;
  totalOpen: number;
}) {
  const { to, name, overdue, dueToday, totalOpen } = params;

  function taskRow(task: { id: string; title: string; priority: string; dueDate?: Date | null }) {
    return `
      <tr>
        <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;">
          <a href="${APP_URL}/tasks/${task.id}" style="color:${BRAND_COLOR};text-decoration:none;font-weight:500;">${task.title}</a>
        </td>
        <td style="padding:8px 0 8px 12px;border-bottom:1px solid #f3f4f6;white-space:nowrap;">
          ${priorityBadge(task.priority)}
        </td>
        ${task.dueDate ? `<td style="padding:8px 0 8px 12px;border-bottom:1px solid #f3f4f6;color:#6b7280;font-size:13px;white-space:nowrap;">${new Date(task.dueDate).toLocaleDateString()}</td>` : ""}
      </tr>`;
  }

  const overdueSection = overdue.length > 0 ? `
    <h3 style="color:#ef4444;font-size:16px;margin:0 0 8px;font-weight:600;">⚠️ Overdue (${overdue.length})</h3>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      ${overdue.map(taskRow).join("")}
    </table>` : "";

  const dueTodaySection = dueToday.length > 0 ? `
    <h3 style="color:#d97706;font-size:16px;margin:0 0 8px;font-weight:600;">📅 Due Today (${dueToday.length})</h3>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      ${dueToday.map(taskRow).join("")}
    </table>` : "";

  const content = `
    <h2 style="margin:0 0 4px;color:#111827;font-size:20px;">Good morning, ${name}!</h2>
    <p style="color:#6b7280;margin:0 0 24px;font-size:15px;">Here's your SENTASK summary for today.</p>
    <div style="display:flex;gap:16px;margin-bottom:24px;">
      <div style="flex:1;background:#f8faff;border:1px solid #e0e7ff;border-radius:10px;padding:16px;text-align:center;">
        <p style="margin:0;color:#4b5563;font-size:13px;font-weight:500;">Open Tasks</p>
        <p style="margin:4px 0 0;color:#1e3a8a;font-size:24px;font-weight:700;">${totalOpen}</p>
      </div>
      <div style="flex:1;background:${overdue.length > 0 ? "#fff5f5" : "#f0fdf4"};border:1px solid ${overdue.length > 0 ? "#fecaca" : "#bbf7d0"};border-radius:10px;padding:16px;text-align:center;">
        <p style="margin:0;color:#4b5563;font-size:13px;font-weight:500;">Overdue</p>
        <p style="margin:4px 0 0;color:${overdue.length > 0 ? "#dc2626" : "#16a34a"};font-size:24px;font-weight:700;">${overdue.length}</p>
      </div>
      <div style="flex:1;background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:16px;text-align:center;">
        <p style="margin:0;color:#4b5563;font-size:13px;font-weight:500;">Due Today</p>
        <p style="margin:4px 0 0;color:#d97706;font-size:24px;font-weight:700;">${dueToday.length}</p>
      </div>
    </div>
    ${overdueSection}
    ${dueTodaySection}
    ${overdue.length === 0 && dueToday.length === 0
      ? `<p style="color:#16a34a;font-size:15px;font-weight:600;text-align:center;">✅ You're all caught up! No overdue or due-today tasks.</p>`
      : ""}
    <div style="text-align:center;margin-top:24px;">
      <a href="${APP_URL}/my-tasks" style="background:${BRAND_COLOR};color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;font-size:15px;display:inline-block;">
        View My Tasks
      </a>
    </div>
  `;

  return sendWorkspaceEmail({
    from: process.env.SMTP_FROM || `SENTASK <noreply@seneca.uz>`,
    to,
    subject: `[SENTASK] Daily Digest — ${new Date().toLocaleDateString()}`,
    html: emailTemplate(content),
  });
}
