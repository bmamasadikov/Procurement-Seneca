import { google } from "googleapis";

export const GOOGLE_WORKSPACE_SCOPES = {
  calendar: "https://www.googleapis.com/auth/calendar.events",
  gmailSend: "https://www.googleapis.com/auth/gmail.send",
  directoryReadonly: "https://www.googleapis.com/auth/admin.directory.user.readonly",
  openId: "openid",
  email: "email",
  profile: "profile",
} as const;

function getServiceAccountEmail() {
  return process.env.GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL || "";
}

function getServiceAccountPrivateKey() {
  return (process.env.GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY || "").replace(/\\n/g, "\n");
}

export function isGoogleWorkspaceServiceAccountConfigured() {
  return Boolean(getServiceAccountEmail() && getServiceAccountPrivateKey());
}

export function createDelegatedGoogleJwt(params: {
  subject: string;
  scopes: string[];
}) {
  const clientEmail = getServiceAccountEmail();
  const privateKey = getServiceAccountPrivateKey();

  if (!clientEmail || !privateKey) {
    throw new Error(
      "Google Workspace service account is not configured. Set GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL and GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY."
    );
  }

  return new google.auth.JWT({
    email: clientEmail,
    key: privateKey,
    scopes: params.scopes,
    subject: params.subject,
  });
}

export async function getDelegatedGoogleAuth(params: {
  subject: string;
  scopes: string[];
}) {
  const auth = createDelegatedGoogleJwt(params);
  await auth.authorize();
  return auth;
}

export function getGoogleWorkspaceDelegatedAdminEmail() {
  return process.env.GOOGLE_WORKSPACE_DELEGATED_ADMIN_EMAIL || "";
}
