import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canManageTasks } from "@/lib/access";

export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!canManageTasks(session.user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const users = await prisma.user.findMany({
    where: { isActive: true, role: { not: "PENDING" } },
    select: {
      id: true, name: true, email: true, avatarUrl: true, jobTitle: true,
      departmentId: true,
      department: { select: { name: true, color: true } },
      assignedTasks: {
        where: { isArchived: false },
        select: { id: true, status: true, priority: true, dueDate: true, isOverdue: true },
      },
    },
    orderBy: { name: "asc" },
  });

  const workload = users.map((u) => {
    const tasks = u.assignedTasks;
    const total = tasks.length;
    const done = tasks.filter((t) => t.status === "DONE").length;
    const overdue = tasks.filter((t) => t.isOverdue && t.status !== "DONE").length;
    const inProgress = tasks.filter((t) => t.status === "IN_PROGRESS").length;
    const todo = tasks.filter((t) => t.status === "TODO" || t.status === "BACKLOG" || t.status === "WAITING").length;
    const critical = tasks.filter((t) => t.priority === "CRITICAL" && t.status !== "DONE").length;
    return {
      id: u.id,
      name: u.name,
      email: u.email,
      avatarUrl: u.avatarUrl,
      jobTitle: u.jobTitle,
      department: u.department,
      total, done, overdue, inProgress, todo, critical,
      open: total - done,
    };
  });

  return NextResponse.json(workload);
}
