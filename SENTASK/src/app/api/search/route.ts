import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { hasFullTaskAccess } from "@/lib/access";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const q = req.nextUrl.searchParams.get("q")?.trim() || "";
  if (q.length < 2) return NextResponse.json({ tasks: [], users: [] });

  const taskWhere = hasFullTaskAccess(session.user)
    ? { isArchived: false }
    : {
        isArchived: false,
        OR: [{ assigneeId: session.user.id }, { creatorId: session.user.id }],
      };

  const [tasks, users] = await Promise.all([
    prisma.task.findMany({
      where: {
        ...taskWhere,
        OR: [
          { title: { contains: q, mode: "insensitive" } },
          { description: { contains: q, mode: "insensitive" } },
          { customTitle: { contains: q, mode: "insensitive" } },
        ],
      },
      select: {
        id: true, title: true, status: true, priority: true, dueDate: true,
        assignee: { select: { id: true, name: true } },
      },
      orderBy: { updatedAt: "desc" },
      take: 8,
    }),
    hasFullTaskAccess(session.user)
      ? prisma.user.findMany({
          where: {
            isActive: true,
            OR: [
              { name: { contains: q, mode: "insensitive" } },
              { email: { contains: q, mode: "insensitive" } },
            ],
          },
          select: { id: true, name: true, email: true, jobTitle: true, role: true },
          take: 4,
        })
      : Promise.resolve([]),
  ]);

  return NextResponse.json({ tasks, users });
}
