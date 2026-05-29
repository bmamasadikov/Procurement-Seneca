import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, formatDistanceToNow, isPast, isToday } from "date-fns";
import { Priority, TaskStatus } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return "—";
  return format(new Date(date), "MMM d, yyyy");
}

export function formatDateTime(date: string | Date | null | undefined): string {
  if (!date) return "—";
  return format(new Date(date), "MMM d, yyyy HH:mm");
}

export function formatRelative(date: string | Date | null | undefined): string {
  if (!date) return "—";
  return formatDistanceToNow(new Date(date), { addSuffix: true });
}

export function isOverdue(dueDate: string | Date | null | undefined, status: TaskStatus): boolean {
  if (!dueDate || status === "DONE") return false;
  return isPast(new Date(dueDate)) && !isToday(new Date(dueDate));
}

export function isDueToday(dueDate: string | Date | null | undefined): boolean {
  if (!dueDate) return false;
  return isToday(new Date(dueDate));
}

export const PRIORITY_CONFIG: Record<Priority, { label: string; color: string; bg: string; border: string }> = {
  CRITICAL: { label: "Critical", color: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
  HIGH: { label: "High", color: "text-orange-700", bg: "bg-orange-50", border: "border-orange-200" },
  MEDIUM: { label: "Medium", color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200" },
  LOW: { label: "Low", color: "text-gray-600", bg: "bg-gray-50", border: "border-gray-200" },
};

export const STATUS_CONFIG: Record<TaskStatus, { label: string; color: string; bg: string; dot: string }> = {
  BACKLOG: { label: "Backlog", color: "text-gray-600", bg: "bg-gray-100", dot: "bg-gray-400" },
  TODO: { label: "To Do", color: "text-blue-700", bg: "bg-blue-50", dot: "bg-blue-500" },
  IN_PROGRESS: { label: "In Progress", color: "text-yellow-700", bg: "bg-yellow-50", dot: "bg-yellow-500" },
  WAITING: { label: "Waiting", color: "text-purple-700", bg: "bg-purple-50", dot: "bg-purple-500" },
  DONE: { label: "Done", color: "text-green-700", bg: "bg-green-50", dot: "bg-green-500" },
};

export const REPEAT_LABELS: Record<string, string> = {
  NONE: "One-time",
  DAILY: "Daily",
  WEEKLY: "Weekly",
  MONTHLY: "Monthly",
};

export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val !== undefined && val !== "" && val !== null) {
      query.set(key, String(val));
    }
  }
  return query.toString();
}

export const EMAIL_RECIPIENTS = [
  { label: "Tulkin (Manager)", value: "tulkin@seneca.uz" },
  { label: "Sales Team", value: "sales@seneca.uz" },
  { label: "Customer Care", value: "care@seneca.uz" },
];
