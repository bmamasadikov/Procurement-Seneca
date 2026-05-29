import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canAccessTask, canManageTasks } from "@/lib/access";
import { z } from "zod";

const createSchema = z.object({
  dependsOnId: z.string(),
});

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task || !canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const deps = await prisma.taskDependency.findMany({
    where: { taskId: params.id },
    include: {
      dependsOn: {
        select: { id: true, title: true, status: true, priority: true, dueDate: true, assignee: { select: { id: true, name: true } } },
      },
    },
  });

  // Also get tasks that block this task (reverse direction)
  const blockers = await prisma.taskDependency.findMany({
    where: { dependsOnId: params.id },
    include: {
      task: {
        select: { id: true, title: true, status: true, priority: true },
      },
    },
  });

  return NextResponse.json({ blockedBy: deps.map((d) => d.dependsOn), blocking: blockers.map((b) => b.task) });
}

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!canManageTasks(session.user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task || !canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const body = await req.json();
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: "Validation failed" }, { status: 422 });

  if (parsed.data.dependsOnId === params.id) {
    return NextResponse.json({ error: "A task cannot depend on itself" }, { status: 400 });
  }

  const blocker = await prisma.task.findUnique({ where: { id: parsed.data.dependsOnId } });
  if (!blocker) return NextResponse.json({ error: "Blocking task not found" }, { status: 404 });

  const dep = await prisma.taskDependency.upsert({
    where: { taskId_dependsOnId: { taskId: params.id, dependsOnId: parsed.data.dependsOnId } },
    update: {},
    create: { taskId: params.id, dependsOnId: parsed.data.dependsOnId },
  });

  return NextResponse.json(dep, { status: 201 });
}
