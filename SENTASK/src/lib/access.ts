import { Role } from "@/types";

function getMasterAccountEmails(): string[] {
  return (process.env.MASTER_ACCOUNT_EMAILS || "")
    .split(",")
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean);
}

type AccessUser = {
  id?: string | null;
  email?: string | null;
  googleEmail?: string | null;
  role?: Role | null;
  isMasterAccount?: boolean | null;
};

type TaskAccessRecord = {
  assigneeId?: string | null;
  creatorId?: string | null;
};

export function normalizeEmail(email?: string | null) {
  return (email || "").trim().toLowerCase();
}

export function isMasterAccountEmail(email?: string | null) {
  const normalized = normalizeEmail(email);
  return Boolean(normalized) && getMasterAccountEmails().includes(normalized);
}

export function hasFullTaskAccess(user?: AccessUser | null) {
  if (!user) return false;

  return (
    Boolean(user.isMasterAccount) ||
    isMasterAccountEmail(user.email) ||
    isMasterAccountEmail(user.googleEmail)
  );
}

export function canManageTasks(user?: AccessUser | null) {
  if (!user) return false;
  return hasFullTaskAccess(user) || user.role === "ADMIN" || user.role === "MANAGER";
}

export function canAccessTask(user?: AccessUser | null, task?: TaskAccessRecord | null) {
  if (!user || !task) return false;
  if (hasFullTaskAccess(user)) return true;
  if (!user.id) return false;

  return task.assigneeId === user.id || task.creatorId === user.id;
}
