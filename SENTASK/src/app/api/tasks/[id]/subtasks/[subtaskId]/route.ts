import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canAccessTask } from "@/lib/access";
import { z } from "zod";

const updateSchema = z.object({
  title: z.string().min(1).max(255).optional(),
  isDone: z.boolean().optional(),
});

type Params = { params: { id: string; subtaskId: string } };

async function getSubTaskAndVerify(taskId: string, subtaskId: string, sessionUser: any) {
  const [task, subTask] = await Promise.all([
    prisma.task.findUnique({ where: { id: taskId } }),
    prisma.subTask.findUnique({ where: { id: subtaskId } }),
  ]);
  if (!task || !subTask || subTask.taskId !== taskId) return null;
  if (!canAccessTask(sessionUser, task)) return null;
  return subTask;
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const subTask = await getSubTaskAndVerify(params.id, params.subtaskId, session.user);
  if (!subTask) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const body = await req.json();
  const parsed = updateSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: "Validation failed" }, { status: 422 });

  const updated = await prisma.subTask.update({
    where: { id: params.subtaskId },
    data: parsed.data,
  });
  return NextResponse.json(updated);
}

export async function DELETE(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const subTask = await getSubTaskAndVerify(params.id, params.subtaskId, session.user);
  if (!subTask) return NextResponse.json({ error: "Not found" }, { status: 404 });

  await prisma.subTask.delete({ where: { id: params.subtaskId } });
  return NextResponse.json({ success: true });
}
