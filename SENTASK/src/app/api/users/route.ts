import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { sendInviteEmail } from "@/lib/email";
import { randomBytes } from "crypto";
import { z } from "zod";

const createUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
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

  const { name, email, role, departmentId, jobTitle, phone } = parsed.data;

  const exists = await prisma.user.findUnique({ where: { email } });
  if (exists) return NextResponse.json({ error: "Email already in use" }, { status: 409 });

  // Create user as inactive — they activate via the invite email
  const user = await prisma.user.create({
    data: {
      name,
      email,
      role,
      departmentId: departmentId || null,
      jobTitle,
      phone,
      isActive: false,
    },
    select: {
      id: true, name: true, email: true, googleEmail: true, role: true, authProvider: true, isActive: true,
      jobTitle: true, phone: true, departmentId: true, department: true, createdAt: true,
    },
  });

  // Generate a 7-day invite token (reuses the PasswordReset table)
  const token = randomBytes(32).toString("hex");
  await prisma.passwordReset.create({
    data: {
      token,
      userId: user.id,
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
    },
  });

  const activateUrl = `${process.env.APP_URL}/reset-password?token=${token}`;

  let emailError: string | null = null;
  try {
    const inviterName = session.user.name || "A Seneca admin";
    await sendInviteEmail({ to: email, name, invitedBy: inviterName, activateUrl });
  } catch (err) {
    console.error("Invite email failed:", err);
    emailError = err instanceof Error ? err.message : "Email delivery failed";
  }

  await prisma.activityLog.create({
    data: { action: "user.invited", userId: session.user.id, details: { email, role } },
  });

  return NextResponse.json(
    { ...user, ...(emailError ? { emailWarning: `Member created but invite email failed: ${emailError}` } : {}) },
    { status: 201 }
  );
}
