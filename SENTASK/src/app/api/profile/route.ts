import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { z } from "zod";

const updateProfileSchema = z.object({
  name: z.string().min(2).max(100).optional(),
  jobTitle: z.string().max(100).optional().nullable(),
  phone: z.string().max(30).optional().nullable(),
  notifyByEmail: z.boolean().optional(),
  notifyByTelegram: z.boolean().optional(),
});

export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const user = await prisma.user.findUnique({
    where: { id: session.user.id },
    select: {
      id: true, name: true, email: true, googleEmail: true,
      role: true, jobTitle: true, phone: true, avatarUrl: true,
      authProvider: true, departmentId: true,
      notifyByEmail: true, notifyByTelegram: true,
      telegramUsername: true, isTelegramLinked: true,
      lastLoginAt: true, createdAt: true,
      department: { select: { id: true, name: true, color: true } },
      _count: { select: { assignedTasks: true, createdTasks: true } },
    },
  });

  if (!user) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(user);
}

export async function PATCH(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const parsed = updateProfileSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed", details: parsed.error.flatten() }, { status: 422 });
  }

  const updated = await prisma.user.update({
    where: { id: session.user.id },
    data: parsed.data,
    select: {
      id: true, name: true, email: true, jobTitle: true, phone: true,
      notifyByEmail: true, notifyByTelegram: true,
    },
  });

  return NextResponse.json(updated);
}
