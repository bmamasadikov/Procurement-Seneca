import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { hasFullTaskAccess } from "@/lib/access";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  if (!hasFullTaskAccess(session.user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { searchParams } = new URL(req.url);
  const from = searchParams.get("from");
  const to = searchParams.get("to");
  const departmentId = searchParams.get("departmentId");

  const dateFilter: { gte?: Date; lte?: Date } = {};
  if (from) dateFilter.gte = new Date(from);
  if (to) dateFilter.lte = new Date(to);

  const taskWhere = {
    isArchived: false,
    ...(Object.keys(dateFilter).length ? { createdAt: dateFilter } : {}),
    ...(departmentId ? { departmentId } : {}),
  };

  const now = new Date();

  // Dashboard stats — single groupBy replaces 6 separate count() calls
  const [statusCounts, overdueCount] = await Promise.all([
    prisma.task.groupBy({
      by: ["status"],
      where: taskWhere,
      _count: { _all: true },
    }),
    prisma.task.count({
      where: { ...taskWhere, dueDate: { lt: now }, status: { notIn: ["DONE"] } },
    }),
  ]);

  const countByStatus = Object.fromEntries(statusCounts.map((s) => [s.status, s._count._all]));
  const stats = {
    total: statusCounts.reduce((sum, s) => sum + s._count._all, 0),
    backlog: countByStatus["BACKLOG"] ?? 0,
    todo: countByStatus["TODO"] ?? 0,
    inProgress: countByStatus["IN_PROGRESS"] ?? 0,
    waiting: countByStatus["WAITING"] ?? 0,
    done: countByStatus["DONE"] ?? 0,
    overdue: overdueCount,
  };

  // Employee stats — DB aggregation, no full task rows loaded into memory
  const [users, taskCountsByUser, overdueByUser] = await Promise.all([
    prisma.user.findMany({
      where: { isActive: true },
      select: {
        id: true,
        name: true,
        jobTitle: true,
        department: { select: { name: true, color: true } },
      },
      orderBy: { name: "asc" },
    }),
    prisma.task.groupBy({
      by: ["assigneeId", "status"],
      where: { ...taskWhere, assigneeId: { not: null } },
      _count: { _all: true },
    }),
    prisma.task.groupBy({
      by: ["assigneeId"],
      where: {
        ...taskWhere,
        assigneeId: { not: null },
        dueDate: { lt: now },
        status: { notIn: ["DONE"] },
      },
      _count: { _all: true },
    }),
  ]);

  const userStatusCounts: Record<string, Record<string, number>> = {};
  for (const row of taskCountsByUser) {
    if (!row.assigneeId) continue;
    (userStatusCounts[row.assigneeId] ??= {})[row.status] = row._count._all;
  }
  const userOverdueCounts: Record<string, number> = {};
  for (const row of overdueByUser) {
    if (row.assigneeId) userOverdueCounts[row.assigneeId] = row._count._all;
  }

  const employeeStats = users
    .map((u) => {
      const statusMap = userStatusCounts[u.id] ?? {};
      const total = Object.values(statusMap).reduce((s, c) => s + c, 0);
      const done = statusMap["DONE"] ?? 0;
      return {
        id: u.id,
        name: u.name,
        jobTitle: u.jobTitle,
        department: u.department?.name,
        departmentColor: u.department?.color,
        total,
        done,
        inProgress: statusMap["IN_PROGRESS"] ?? 0,
        overdue: userOverdueCounts[u.id] ?? 0,
        completionRate: total > 0 ? Math.round((done / total) * 100) : 0,
      };
    })
    .filter((e) => e.total > 0);

  // Department stats — same aggregation approach
  const [departments, taskCountsByDept, overdueByDept] = await Promise.all([
    prisma.department.findMany({
      where: { isActive: true },
      select: { id: true, name: true, color: true },
    }),
    prisma.task.groupBy({
      by: ["departmentId", "status"],
      where: { ...taskWhere, departmentId: { not: null } },
      _count: { _all: true },
    }),
    prisma.task.groupBy({
      by: ["departmentId"],
      where: {
        ...taskWhere,
        departmentId: { not: null },
        dueDate: { lt: now },
        status: { notIn: ["DONE"] },
      },
      _count: { _all: true },
    }),
  ]);

  const deptStatusCounts: Record<string, Record<string, number>> = {};
  for (const row of taskCountsByDept) {
    if (!row.departmentId) continue;
    (deptStatusCounts[row.departmentId] ??= {})[row.status] = row._count._all;
  }
  const deptOverdueCounts: Record<string, number> = {};
  for (const row of overdueByDept) {
    if (row.departmentId) deptOverdueCounts[row.departmentId] = row._count._all;
  }

  const deptStats = departments
    .map((d) => {
      const statusMap = deptStatusCounts[d.id] ?? {};
      const total = Object.values(statusMap).reduce((s, c) => s + c, 0);
      const done = statusMap["DONE"] ?? 0;
      return {
        id: d.id,
        name: d.name,
        color: d.color,
        total,
        done,
        overdue: deptOverdueCounts[d.id] ?? 0,
        completionRate: total > 0 ? Math.round((done / total) * 100) : 0,
      };
    })
    .filter((d) => d.total > 0);

  // Recent activity
  const recentActivity = await prisma.activityLog.findMany({
    where: { action: { startsWith: "task." } },
    include: {
      user: { select: { name: true, avatarUrl: true } },
      task: { select: { title: true } },
    },
    orderBy: { createdAt: "desc" },
    take: 20,
  });

  return NextResponse.json({ stats, employeeStats, deptStats, recentActivity });
}
