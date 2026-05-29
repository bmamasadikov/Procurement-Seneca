import nodemailer from "nodemailer";
import { google } from "googleapis";
import { getDefaultSenderEmail, getGoogleWorkspaceSettings } from "@/lib/settings";
import { getDelegatedGoogleAuth, GOOGLE_WORKSPACE_SCOPES } from "@/lib/google/workspace";

export type WorkspaceEmailPayload = {
  to: string | string[];
  subject: string;
  html: string;
  text?: string;
  from?: string;
};

export type WorkspaceEmailResult = {
  provider: "GMAIL_API" | "SMTP";
  providerMessageId?: string;
};

function createSmtpTransport() {
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST || "smtp.gmail.com",
    port: parseInt(process.env.SMTP_PORT || "587", 10),
    secure: process.env.SMTP_SECURE === "true",
    auth: {
      user: process.env.SMTP_USER,
      pass: process.env.SMTP_PASS,
    },
  });
}

function toBase64Url(input: string) {
  return Buffer.from(input)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function extractEmailAddress(from: string) {
  const match = from.match(/<([^>]+)>/);
  return match ? match[1] : from.trim();
}

function buildRawMimeMessage(payload: Required<WorkspaceEmailPayload>) {
  const recipients = Array.isArray(payload.to) ? payload.to : [payload.to];

  return [
    `From: ${payload.from}`,
    `To: ${recipients.join(", ")}`,
    "MIME-Version: 1.0",
    `Subject: ${payload.subject}`,
    'Content-Type: text/html; charset="UTF-8"',
    "",
    payload.html,
  ].join("\r\n");
}

async function sendWithGmailApi(payload: Required<WorkspaceEmailPayload>): Promise<WorkspaceEmailResult> {
  const senderEmail = extractEmailAddress(payload.from);
  const auth = await getDelegatedGoogleAuth({
    subject: senderEmail,
    scopes: [GOOGLE_WORKSPACE_SCOPES.gmailSend],
  });
  const gmail = google.gmail({ version: "v1", auth });
  const raw = toBase64Url(buildRawMimeMessage(payload));

  const response = await gmail.users.messages.send({
    userId: "me",
    requestBody: { raw },
  });

  return {
    provider: "GMAIL_API",
    providerMessageId: response.data.id || undefined,
  };
}

async function sendWithSmtp(payload: Required<WorkspaceEmailPayload>): Promise<WorkspaceEmailResult> {
  const transporter = createSmtpTransport();
  const info = await transporter.sendMail(payload);

  return {
    provider: "SMTP",
    providerMessageId: info.messageId,
  };
}

export async function sendWorkspaceEmail(payload: WorkspaceEmailPayload) {
  const settings = await getGoogleWorkspaceSettings();
  const sender = payload.from || (await getDefaultSenderEmail());
  const normalizedPayload: Required<WorkspaceEmailPayload> = {
    ...payload,
    from: sender,
    text: payload.text || "",
  };

  if (settings.gmailSendingMode === "GMAIL_API") {
    try {
      return await sendWithGmailApi(normalizedPayload);
    } catch (error) {
      if (!process.env.SMTP_HOST) throw error;
      return sendWithSmtp(normalizedPayload);
    }
  }

  return sendWithSmtp(normalizedPayload);
}
