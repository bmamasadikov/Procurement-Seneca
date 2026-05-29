export type Role = "ADMIN" | "MANAGER" | "STAFF" | "PENDING";
export type AuthProvider = "CREDENTIALS" | "GOOGLE";
export type TaskStatus = "BACKLOG" | "TODO" | "IN_PROGRESS" | "WAITING" | "DONE";
export type Priority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type RepeatType = "NONE" | "DAILY" | "WEEKLY" | "MONTHLY";
export type NotificationType =
  | "TASK_ASSIGNED" | "TASK_UPDATED" | "TASK_STATUS_CHANGED"
  | "TASK_COMPLETED" | "TASK_OVERDUE" | "TASK_DUE_SOON"
  | "COMMENT_ADDED" | "MENTIONED" | "RECURRING_REMINDER";
export type NotificationChannel = "IN_APP" | "EMAIL" | "TELEGRAM";
export type NotificationProvider = "IN_APP" | "SMTP" | "GMAIL_API" | "TELEGRAM_BOT";
export type NotificationStatus = "PENDING" | "SENT" | "FAILED" | "SKIPPED";
export type CalendarSyncStatus = "NONE" | "SYNCED" | "FAILED" | "OUTDATED";
export type GmailSendingMode = "SMTP" | "GMAIL_API";
export type CalendarCompletionBehavior = "KEEP" | "MARK_DONE" | "DELETE";

export interface User {
  id: string;
  name: string;
  email: string;
  googleEmail?: string | null;
  googleId?: string | null;
  isMasterAccount?: boolean;
  authProvider?: AuthProvider;
  role: Role;
  isActive: boolean;
  avatarUrl?: string | null;
  phone?: string | null;
  jobTitle?: string | null;
  telegramChatId?: string | null;
  telegramUsername?: string | null;
  isTelegramLinked?: boolean;
  notifyByEmail?: boolean;
  notifyByTelegram?: boolean;
  googleDomain?: string | null;
  googleCalendarId?: string | null;
  lastLoginAt?: string | null;
  createdAt: string;
  departmentId?: string | null;
  department?: Department | null;
}

export interface Department {
  id: string;
  name: string;
  description?: string | null;
  color: string;
  isActive: boolean;
  _count?: { users: number; tasks: number };
}

export interface TaskTemplate {
  id: string;
  name: string;
  description?: string | null;
  isSystem: boolean;
  isActive: boolean;
  sortOrder: number;
}

export interface Task {
  id: string;
  title: string;
  customTitle?: string | null;
  description?: string | null;
  status: TaskStatus;
  priority: Priority;
  repeatType: RepeatType;
  dueDate?: string | null;
  startDate?: string | null;
  reminderAt?: string | null;
  completedAt?: string | null;
  notes?: string | null;
  isArchived: boolean;
  isOverdue: boolean;
  // Notification settings
  notifyEmail: boolean;
  notifyTelegram: boolean;
  notifyEmailAddress?: string | null;
  createCalendarEvent?: boolean;
  googleCalendarEventId?: string | null;
  googleCalendarId?: string | null;
  googleCalendarHtmlLink?: string | null;
  calendarSyncStatus?: CalendarSyncStatus;
  calendarSyncError?: string | null;
  calendarLastSyncedAt?: string | null;
  emailRecipients: string[];
  createdAt: string;
  updatedAt: string;
  coAssigneeIds?: string[];
  coAssignees?: User[];
  templateId?: string | null;
  template?: TaskTemplate | null;
  assigneeId?: string | null;
  assignee?: User | null;
  creatorId: string;
  creator: User;
  departmentId?: string | null;
  department?: Department | null;
  parentTaskId?: string | null;
  _count?: { comments: number; attachments: number };
}

export interface TaskComment {
  id: string;
  content: string;
  createdAt: string;
  updatedAt: string;
  taskId: string;
  authorId: string;
  author: User;
}

export interface TaskAttachment {
  id: string;
  filename: string;
  originalName: string;
  mimeType: string;
  size: number;
  url: string;
  createdAt: string;
  taskId: string;
}

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  isRead: boolean;
  readAt?: string | null;
  createdAt: string;
  userId: string;
  taskId?: string | null;
  task?: Pick<Task, "id" | "title"> | null;
}

export interface NotificationLog {
  id: string;
  channel: NotificationChannel;
  provider?: NotificationProvider;
  type: NotificationType;
  status: NotificationStatus;
  recipient: string;
  subject?: string | null;
  body: string;
  errorMessage?: string | null;
  sentAt?: string | null;
  createdAt: string;
  userId?: string | null;
  taskId?: string | null;
}

export interface ActivityLog {
  id: string;
  action: string;
  field?: string | null;
  oldValue?: string | null;
  newValue?: string | null;
  details?: any;
  createdAt: string;
  userId?: string | null;
  user?: Pick<User, "id" | "name" | "avatarUrl"> | null;
  taskId?: string | null;
}

export interface DashboardStats {
  total: number;
  backlog: number;
  todo: number;
  inProgress: number;
  waiting: number;
  done: number;
  overdue: number;
  dueToday: number;
}

export interface TaskFilters {
  search?: string;
  status?: TaskStatus | "";
  priority?: Priority | "";
  assigneeId?: string;
  departmentId?: string;
  repeatType?: RepeatType | "";
  dueDateFrom?: string;
  dueDateTo?: string;
  templateId?: string;
  overdue?: boolean;
  dueToday?: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  error: string;
  details?: string;
}

export interface GoogleWorkspaceSettings {
  allowedDomains: string[];
  autoProvisionUsers: boolean;
  adminApprovalRequired: boolean;
  calendarSyncEnabled: boolean;
  defaultCreateCalendarEvents: boolean;
  defaultCalendarId: string;
  calendarCompletionBehavior: CalendarCompletionBehavior;
  reminderMinutesBefore: number;
  gmailSendingMode: GmailSendingMode;
  defaultSenderEmail: string;
  directorySyncEnabled: boolean;
  driveAttachmentsEnabled: boolean;
  googleClientConfigured: boolean;
  googleServiceAccountConfigured: boolean;
}
