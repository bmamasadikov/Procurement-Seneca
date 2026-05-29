import {
  PrismaClient, Role, Priority, TaskStatus, RepeatType,
  NotificationType, NotificationChannel, NotificationStatus,
} from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  console.log("🌱 Seeding SENTASK v2 database...");

  // ── Departments ────────────────────────────────────────────────
  const [sales, ops, care, mgmt, finance, marketing] = await Promise.all([
    upsertDept("Sales", "Sales & Revenue team", "#3b82f6"),
    upsertDept("Operations", "Day-to-day operations", "#10b981"),
    upsertDept("Customer Care", "Guest relations team", "#f59e0b"),
    upsertDept("Management", "Leadership & management", "#8b5cf6"),
    upsertDept("Finance", "Finance & accounting", "#ef4444"),
    upsertDept("Marketing", "Marketing & branding", "#06b6d4"),
  ]);

  // ── Task Templates ────────────────────────────────────────────
  const templates = [
    { name: "Reply Reviews", description: "Reply to guest reviews on OTA platforms", isSystem: true, sortOrder: 1 },
    { name: "Update Extranet", description: "Update availability on booking extranets", isSystem: true, sortOrder: 2 },
    { name: "Update Rate", description: "Update pricing rates on all channels", isSystem: true, sortOrder: 3 },
    { name: "Custom", description: "Custom task — enter title manually", isSystem: true, sortOrder: 99 },
  ];
  for (const t of templates) {
    await prisma.taskTemplate.upsert({ where: { name: t.name }, update: {}, create: t });
  }
  const [tmplReviews, tmplExtranet, tmplRate, tmplCustom] = await Promise.all([
    prisma.taskTemplate.findFirst({ where: { name: "Reply Reviews" } }),
    prisma.taskTemplate.findFirst({ where: { name: "Update Extranet" } }),
    prisma.taskTemplate.findFirst({ where: { name: "Update Rate" } }),
    prisma.taskTemplate.findFirst({ where: { name: "Custom" } }),
  ]);

  // ── Users ────────────────────────────────────────────────────
  const adminHash = await bcrypt.hash("admin123", 12);
  const managerHash = await bcrypt.hash("manager123", 12);
  const staffHash = await bcrypt.hash("staff123", 12);

  const admin = await prisma.user.upsert({
    where: { email: "admin@seneca.uz" },
    update: {},
    create: {
      name: "Admin User", email: "admin@seneca.uz", passwordHash: adminHash,
      role: Role.ADMIN, jobTitle: "System Administrator", departmentId: mgmt.id,
      notifyByEmail: true, notifyByTelegram: false,
    },
  });

  const tulkin = await prisma.user.upsert({
    where: { email: "tulkin@seneca.uz" },
    update: {
      name: "Tulkin Radjabov",
      role: Role.MANAGER,
      jobTitle: "CEO",
      departmentId: mgmt.id,
    },
    create: {
      name: "Tulkin Radjabov", email: "tulkin@seneca.uz", passwordHash: managerHash,
      role: Role.MANAGER, jobTitle: "CEO", departmentId: mgmt.id,
      telegramChatId: "123456789", telegramUsername: "@tulkin_ops",
      notifyByEmail: true, notifyByTelegram: true, isTelegramLinked: true,
    },
  });

  await prisma.user.upsert({
    where: { email: "bekhroz@seneca.uz" },
    update: {
      name: "Bekhroz Mamasadikov",
      role: Role.MANAGER,
      jobTitle: "COO",
      departmentId: mgmt.id,
    },
    create: {
      name: "Bekhroz Mamasadikov", email: "bekhroz@seneca.uz", passwordHash: managerHash,
      role: Role.MANAGER, jobTitle: "COO", departmentId: mgmt.id,
      notifyByEmail: true, notifyByTelegram: false,
    },
  });

  const salesUser = await prisma.user.upsert({
    where: { email: "sales@seneca.uz" },
    update: {},
    create: {
      name: "Dilnoza Karimova", email: "sales@seneca.uz", passwordHash: staffHash,
      role: Role.STAFF, jobTitle: "Sales Executive", departmentId: sales.id,
      telegramChatId: "987654321", telegramUsername: "@dilnoza_sales",
      notifyByEmail: true, notifyByTelegram: true, isTelegramLinked: true,
    },
  });

  const careUser = await prisma.user.upsert({
    where: { email: "care@seneca.uz" },
    update: {},
    create: {
      name: "Maftuna Rahimova", email: "care@seneca.uz", passwordHash: staffHash,
      role: Role.STAFF, jobTitle: "Customer Care Specialist", departmentId: care.id,
      notifyByEmail: true, notifyByTelegram: false,
    },
  });

  const financeUser = await prisma.user.upsert({
    where: { email: "finance@seneca.uz" },
    update: {},
    create: {
      name: "Jasur Toshmatov", email: "finance@seneca.uz", passwordHash: staffHash,
      role: Role.STAFF, jobTitle: "Finance Analyst", departmentId: finance.id,
      notifyByEmail: true, notifyByTelegram: false,
    },
  });

  // ── Tasks ──────────────────────────────────────────────────
  const now = new Date();
  const daysAgo = (n: number) => new Date(now.getTime() - n * 86400000);
  const daysFromNow = (n: number) => new Date(now.getTime() + n * 86400000);

  const tasksData = [
    {
      title: "Reply to Booking.com reviews",
      description: "Reply to all pending guest reviews on Booking.com — minimum 5 reviews. Use professional tone and address specific feedback.",
      status: TaskStatus.IN_PROGRESS, priority: Priority.HIGH,
      repeatType: RepeatType.DAILY,
      dueDate: daysFromNow(1),
      reminderAt: daysFromNow(0),
      assigneeId: salesUser.id, creatorId: tulkin.id, departmentId: sales.id,
      templateId: tmplReviews?.id,
      notifyEmail: true, notifyTelegram: true,
      emailRecipients: ["tulkin@seneca.uz"],
    },
    {
      title: "Update Expedia rates for next week",
      description: "Adjust pricing on Expedia extranet for the upcoming week based on market analysis and demand forecast.",
      status: TaskStatus.TODO, priority: Priority.CRITICAL,
      repeatType: RepeatType.WEEKLY,
      dueDate: daysFromNow(2),
      reminderAt: daysFromNow(1),
      assigneeId: careUser.id, creatorId: tulkin.id, departmentId: ops.id,
      templateId: tmplRate?.id,
      notifyEmail: true, notifyTelegram: false,
      emailRecipients: ["sales@seneca.uz"],
    },
    {
      title: "Monthly performance report",
      description: "Prepare and submit monthly performance report including all KPIs, revenue data, and team productivity metrics.",
      status: TaskStatus.BACKLOG, priority: Priority.MEDIUM,
      repeatType: RepeatType.MONTHLY,
      dueDate: daysFromNow(14),
      assigneeId: tulkin.id, creatorId: admin.id, departmentId: mgmt.id,
      notifyEmail: true, notifyTelegram: false,
      emailRecipients: [],
    },
    {
      title: "Respond to guest complaint — Room 203",
      description: "Guest reported AC malfunction and water pressure issues. Follow up with engineering, confirm resolution, and close complaint formally.",
      status: TaskStatus.WAITING, priority: Priority.HIGH,
      repeatType: RepeatType.NONE,
      dueDate: daysFromNow(0),
      reminderAt: daysAgo(1),
      assigneeId: careUser.id, creatorId: tulkin.id, departmentId: care.id,
      notifyEmail: true, notifyTelegram: true,
      emailRecipients: [],
    },
    {
      title: "Update Airbnb listing photos",
      description: "Upload new seasonal photos to all Airbnb listings. Include exterior, rooms, and amenities. Ensure high resolution.",
      status: TaskStatus.DONE, priority: Priority.LOW,
      repeatType: RepeatType.NONE,
      dueDate: daysAgo(2),
      completedAt: daysAgo(1),
      assigneeId: salesUser.id, creatorId: tulkin.id, departmentId: sales.id,
      templateId: tmplCustom?.id,
      notifyEmail: false, notifyTelegram: false,
      emailRecipients: [],
    },
    {
      title: "Update extranet availability — May",
      description: "Block unavailable dates on all OTA extranets for May. Coordinate with operations team for maintenance windows.",
      status: TaskStatus.TODO, priority: Priority.HIGH,
      repeatType: RepeatType.MONTHLY,
      dueDate: daysFromNow(3),
      assigneeId: salesUser.id, creatorId: tulkin.id, departmentId: sales.id,
      templateId: tmplExtranet?.id,
      notifyEmail: true, notifyTelegram: true,
      emailRecipients: ["tulkin@seneca.uz", "care@seneca.uz"],
    },
    {
      title: "Finance reconciliation — Q1",
      description: "Complete Q1 financial reconciliation. Verify all transactions against bank statements and submit to management.",
      status: TaskStatus.IN_PROGRESS, priority: Priority.CRITICAL,
      repeatType: RepeatType.NONE,
      dueDate: daysFromNow(5),
      assigneeId: financeUser.id, creatorId: admin.id, departmentId: finance.id,
      notifyEmail: true, notifyTelegram: false,
      emailRecipients: ["admin@seneca.uz"],
    },
    {
      // OVERDUE TASK
      title: "Submit marketing materials for review",
      description: "Prepare and submit all marketing materials for management review including brochures, social media assets, and email templates.",
      status: TaskStatus.IN_PROGRESS, priority: Priority.HIGH,
      repeatType: RepeatType.NONE,
      dueDate: daysAgo(3),
      isOverdue: true,
      assigneeId: salesUser.id, creatorId: tulkin.id, departmentId: marketing.id,
      notifyEmail: true, notifyTelegram: false,
      emailRecipients: [],
    },
    {
      // OVERDUE TASK
      title: "Daily reply to Care team inquiries",
      description: "Check and respond to all internal inquiries from the Care team within same business day.",
      status: TaskStatus.TODO, priority: Priority.MEDIUM,
      repeatType: RepeatType.DAILY,
      dueDate: daysAgo(1),
      isOverdue: true,
      assigneeId: careUser.id, creatorId: tulkin.id, departmentId: care.id,
      templateId: tmplCustom?.id,
      notifyEmail: true, notifyTelegram: true,
      emailRecipients: [],
    },
    {
      title: "Review and update staff contracts",
      description: "Review all staff employment contracts coming up for renewal in Q2. Prepare renewal documents or termination notices as required.",
      status: TaskStatus.BACKLOG, priority: Priority.LOW,
      repeatType: RepeatType.NONE,
      dueDate: daysFromNow(30),
      assigneeId: admin.id, creatorId: admin.id, departmentId: mgmt.id,
      notifyEmail: true, notifyTelegram: false,
      emailRecipients: [],
    },
  ];

  for (const taskData of tasksData) {
    await prisma.task.create({ data: taskData as any });
  }

  // ── Sample comments ──────────────────────────────────────────
  const firstTask = await prisma.task.findFirst({ where: { assigneeId: salesUser.id, status: "IN_PROGRESS" } });
  if (firstTask) {
    await prisma.taskComment.createMany({
      data: [
        { content: "I've started working on this. Will complete 3 reviews by end of day.", taskId: firstTask.id, authorId: salesUser.id },
        { content: "Good progress! Make sure to address the negative reviews first — priority.", taskId: firstTask.id, authorId: tulkin.id },
        { content: "All 5 reviews replied to. Closing this shortly.", taskId: firstTask.id, authorId: salesUser.id },
      ],
    });
  }

  // ── Seed notifications ────────────────────────────────────────
  await prisma.notification.createMany({
    data: [
      { type: NotificationType.TASK_ASSIGNED, title: "New Task Assigned", message: 'You have been assigned: "Reply to Booking.com reviews"', userId: salesUser.id, isRead: false },
      { type: NotificationType.TASK_OVERDUE, title: "Task Overdue", message: '"Submit marketing materials for review" is overdue', userId: tulkin.id, isRead: false },
      { type: NotificationType.TASK_DUE_SOON, title: "Task Due Today", message: '"Respond to guest complaint — Room 203" is due today', userId: careUser.id, isRead: false },
      { type: NotificationType.COMMENT_ADDED, title: "New Comment", message: 'Dilnoza commented on "Reply to Booking.com reviews"', userId: tulkin.id, isRead: true },
      { type: NotificationType.TASK_ASSIGNED, title: "New Task Assigned", message: 'You have been assigned: "Respond to guest complaint — Room 203"', userId: careUser.id, isRead: true },
    ],
  });

  // ── Seed notification logs ────────────────────────────────────
  const sampleTask = await prisma.task.findFirst({ where: { assigneeId: salesUser.id } });
  if (sampleTask) {
    await prisma.notificationLog.createMany({
      data: [
        { channel: NotificationChannel.EMAIL, type: NotificationType.TASK_ASSIGNED, status: NotificationStatus.SENT, recipient: "sales@seneca.uz", subject: "[SENTASK] New Task: Reply to Booking.com reviews", body: "Task assigned...", sentAt: new Date(), taskId: sampleTask.id },
        { channel: NotificationChannel.TELEGRAM, type: NotificationType.TASK_ASSIGNED, status: NotificationStatus.SENT, recipient: "987654321", body: "📋 New task assigned...", sentAt: new Date(), taskId: sampleTask.id },
        { channel: NotificationChannel.EMAIL, type: NotificationType.TASK_OVERDUE, status: NotificationStatus.SENT, recipient: "sales@seneca.uz", subject: "[SENTASK] Overdue: Submit marketing materials", body: "Task overdue...", sentAt: new Date(), taskId: sampleTask.id },
      ],
    });
  }

  // ── App settings ─────────────────────────────────────────────
  const defaultSettings = [
    { key: "app_name", value: "SENTASK" },
    { key: "company_name", value: "Seneca" },
    { key: "email_sender_name", value: "SENTASK Notifications" },
    { key: "reminder_lead_time_hours", value: "24" },
    { key: "overdue_check_interval_hours", value: "6" },
    { key: "google_workspace.allowed_domains", value: JSON.stringify(["seneca.uz"]) },
    { key: "google_workspace.auto_provision_users", value: "true" },
    { key: "google_workspace.admin_approval_required", value: "true" },
    { key: "google_workspace.calendar_sync_enabled", value: "true" },
    { key: "google_workspace.default_create_calendar_events", value: "false" },
    {
      key: "google_workspace.default_calendar_id",
      value: "c_9d7a3ee7e8637ae4e7026b1514ee9e13a127112dab4b464c2761fb81735b2546@group.calendar.google.com",
    },
    { key: "google_workspace.calendar_completion_behavior", value: "MARK_DONE" },
    { key: "google_workspace.reminder_minutes_before", value: "30" },
    { key: "google_workspace.gmail_sending_mode", value: "GMAIL_API" },
    { key: "google_workspace.default_sender_email", value: "noreply@seneca.uz" },
    { key: "google_workspace.directory_sync_enabled", value: "true" },
    { key: "google_workspace.drive_attachments_enabled", value: "false" },
  ];
  for (const s of defaultSettings) {
    await prisma.appSetting.upsert({ where: { key: s.key }, update: {}, create: s });
  }

  console.log("✅ SENTASK v2 database seeded successfully!");
  console.log("\n📋 Demo credentials:");
  console.log("  Admin:   admin@seneca.uz   / admin123");
  console.log("  Manager: tulkin@seneca.uz  / manager123");
  console.log("  Manager: bekhroz@seneca.uz / manager123");
  console.log("  Staff:   sales@seneca.uz   / staff123");
  console.log("  Staff:   care@seneca.uz    / staff123");
  console.log("  Staff:   finance@seneca.uz / staff123");
}

async function upsertDept(name: string, description: string, color: string) {
  return prisma.department.upsert({
    where: { name },
    update: {},
    create: { name, description, color },
  });
}

main()
  .catch((e) => { console.error(e); process.exit(1); })
  .finally(async () => { await prisma.$disconnect(); });
