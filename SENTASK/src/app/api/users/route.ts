import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import bcrypt from "bcryptjs";
import { z } from "zod";

const createUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  password: z.string().min(6),
  role: z.enum(["ADMIN", "MANAGER", "STAFF", "PENDING"]).default("STAFF"),
  departmentId: z.string().optional().nullable(),
  jobTitle: z.string().optional(),
  phone: z.string().optional(),
});

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const search = searchParams.get("search") || "";
  const departmentId = searchParams.get("departmentId") || "";
  const role = searchParams.get("role") || "";
  const activeOnly = searchParams.get("activeOnly") !== "false";

  const where: any = {};
  if (activeOnly) where.isActive = true;
  if (search) {
    where.OR = [
      { name: { contains: search, mode: "insensitive" } },
      { email: { contains: search, mode: "insensitive" } },
    ];
  }
  if (departmentId) where.departmentId = departmentId;
  if (role) where.role = role;

  const users = await prisma.user.findMany({
    where,
    select: {
      id: true, name: true, email: true, googleEmail: true, role: true, authProvider: true, isActive: true,
      avatarUrl: true, jobTitle: true, phone: true, lastLoginAt: true,
      createdAt: true, departmentId: true, department: true,
    },
    orderBy: { name: "asc" },
  });

  return NextResponse.json(users);
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  if (session.user.role !== "ADMIN") {
    return NextResponse.json({ error: "Forbidden: admin only" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = createUserSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed", details: parsed.error.flatten() }, { status: 422 });
  }

  const { name, email, password, role, departmentId, jobTitle, phone } = parsed.data;

  const exists = await prisma.user.findUnique({ where: { email } });
  if (exists) return NextResponse.json({ error: "Email already in use" }, { status: 409 });

  const passwordHash = await bcrypt.hash(password, 12);

  const user = await prisma.user.create({
    data: { name, email, passwordHash, role, departmentId: departmentId || null, jobTitle, phone },
    select: {
      id: true, name: true, email: true, googleEmail: true, role: true, authProvider: true, isActive: true,
      jobTitle: true, phone: true, departmentId: true, department: true, createdAt: true,
    },
  });

  await prisma.activityLog.create({
    data: { action: "user.created", userId: session.user.id, details: { email, role } },
  });

  return NextResponse.json(user, { status: 201 });
}
