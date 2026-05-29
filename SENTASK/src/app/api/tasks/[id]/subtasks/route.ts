import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canAccessTask } from "@/lib/access";
import { z } from "zod";

const createSchema = z.object({
  title: z.string().min(1).max(255),
});

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task || !canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const subTasks = await prisma.subTask.findMany({
    where: { taskId: params.id },
    orderBy: [{ sortOrder: "asc" }, { createdAt: "asc" }],
  });
  return NextResponse.json(subTasks);
}

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task || !canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const body = await req.json();
  const parsed = createSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: "Validation failed" }, { status: 422 });

  const maxOrder = await prisma.subTask.aggregate({
    where: { taskId: params.id },
    _max: { sortOrder: true },
  });

  const subTask = await prisma.subTask.create({
    data: {
      title: parsed.data.title,
      taskId: params.id,
      sortOrder: (maxOrder._max.sortOrder ?? -1) + 1,
    },
  });
  return NextResponse.json(subTask, { status: 201 });
}
