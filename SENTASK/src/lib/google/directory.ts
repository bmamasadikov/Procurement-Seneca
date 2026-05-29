import { google } from "googleapis";
import { Role } from "@prisma/client";
import { prisma } from "@/lib/prisma";
import { getGoogleWorkspaceDelegatedAdminEmail, getDelegatedGoogleAuth, GOOGLE_WORKSPACE_SCOPES } from "@/lib/google/workspace";
import { getGoogleWorkspaceSettings } from "@/lib/settings";

export async function listWorkspaceDirectoryUsers(limit = 100) {
  const delegatedAdmin = getGoogleWorkspaceDelegatedAdminEmail();
  if (!delegatedAdmin) {
    throw new Error(
      "GOOGLE_WORKSPACE_DELEGATED_ADMIN_EMAIL is required for Google Workspace directory sync."
    );
  }

  const auth = await getDelegatedGoogleAuth({
    subject: delegatedAdmin,
    scopes: [GOOGLE_WORKSPACE_SCOPES.directoryReadonly],
  });
  const admin = google.admin({ version: "directory_v1", auth });
  const settings = await getGoogleWorkspaceSettings();
  const primaryDomain = settings.allowedDomains[0];

  const response = await admin.users.list({
    customer: "my_customer",
    domain: primaryDomain,
    maxResults: limit,
    orderBy: "email",
  });

  return response.data.users || [];
}

export async function syncWorkspaceDirectoryUsers(limit = 100) {
  const settings = await getGoogleWorkspaceSettings();
  if (!settings.directorySyncEnabled) {
    return { synced: 0, skipped: true };
  }

  const workspaceUsers = await listWorkspaceDirectoryUsers(limit);
  let synced = 0;

  for (const workspaceUser of workspaceUsers) {
    const email = workspaceUser.primaryEmail?.toLowerCase();
    if (!email) continue;

    const domain = email.split("@")[1] || null;
    const name =
      workspaceUser.name?.fullName ||
      [workspaceUser.name?.givenName, workspaceUser.name?.familyName].filter(Boolean).join(" ") ||
      email;

    const existingUser = await prisma.user.findUnique({
      where: { email },
      select: { id: true, role: true, isActive: true },
    });

    await prisma.user.upsert({
      where: { email },
      update: {
        name,
        avatarUrl: workspaceUser.thumbnailPhotoUrl || undefined,
        googleId: workspaceUser.id || undefined,
        googleEmail: email,
        googleDomain: domain,
        authProvider: existingUser?.role === Role.STAFF || existingUser?.role === Role.MANAGER || existingUser?.role === Role.ADMIN
          ? undefined
          : "GOOGLE",
        lastDirectorySyncAt: new Date(),
      },
      create: {
        name,
        email,
        googleEmail: email,
        googleId: workspaceUser.id || undefined,
        googleDomain: domain,
        avatarUrl: workspaceUser.thumbnailPhotoUrl || undefined,
        authProvider: "GOOGLE",
        role: settings.adminApprovalRequired ? "PENDING" : "STAFF",
        isActive: true,
        lastDirectorySyncAt: new Date(),
      },
    });

    synced++;
  }

  return { synced };
}
