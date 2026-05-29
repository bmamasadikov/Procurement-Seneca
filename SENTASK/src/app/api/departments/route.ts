import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { z } from "zod";

const deptSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().optional(),
  color: z.string().default("#1e3a8a"),
});

export async function GET() {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const departments = await prisma.department.findMany({
    where: { isActive: true },
    include: { _count: { select: { users: true, tasks: true } } },
    orderBy: { name: "asc" },
  });

  return NextResponse.json(departments);
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  if (session.user.role !== "ADMIN") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = deptSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed" }, { status: 422 });
  }

  const dept = await prisma.department.create({ data: parsed.data });
  return NextResponse.json(dept, { status: 201 });
}
