import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canAccessTask } from "@/lib/access";
import { z } from "zod";

const createSchema = z.object({
  minutes: z.number().int().min(1).max(1440),
  note: z.string().max(255).optional().nullable(),
  date: z.string().optional(),
});

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task || !canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const entries = await prisma.timeEntry.findMany({
    where: { taskId: params.id },
    include: { user: { select: { id: true, name: true, avatarUrl: true } } },
    orderBy: { date: "desc" },
  });

  const totalMinutes = entries.reduce((s, e) => s + e.minutes, 0);
  return NextResponse.json({ entries, totalMinutes });
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

  const entry = await prisma.timeEntry.create({
    data: {
      minutes: parsed.data.minutes,
      note: parsed.data.note || null,
      date: parsed.data.date ? new Date(parsed.data.date) : new Date(),
      taskId: params.id,
      userId: session.user.id,
    },
    include: { user: { select: { id: true, name: true, avatarUrl: true } } },
  });

  return NextResponse.json(entry, { status: 201 });
}
