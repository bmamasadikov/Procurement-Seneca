import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import bcrypt from "bcryptjs";
import { z } from "zod";

const updateUserSchema = z.object({
  name: z.string().min(1).max(100).optional(),
  email: z.string().email().optional(),
  password: z.string().min(6).optional(),
  role: z.enum(["ADMIN", "MANAGER", "STAFF", "PENDING"]).optional(),
  departmentId: z.string().optional().nullable(),
  jobTitle: z.string().optional().nullable(),
  phone: z.string().optional().nullable(),
  isActive: z.boolean().optional(),
});

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // Users can update their own profile; admins can update anyone
  const isSelf = session.user.id === params.id;
  const isAdmin = session.user.role === "ADMIN";

  if (!isSelf && !isAdmin) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = updateUserSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed" }, { status: 422 });
  }

  const { password, ...rest } = parsed.data;
  const updates: any = { ...rest };

  // Only admins can change roles
  if (rest.role && !isAdmin) delete updates.role;
  if (rest.isActive !== undefined && !isAdmin) delete updates.isActive;

  if (password) {
    updates.passwordHash = await bcrypt.hash(password, 12);
  }

  const user = await prisma.user.update({
    where: { id: params.id },
    data: updates,
    select: {
      id: true, name: true, email: true, googleEmail: true, role: true, authProvider: true, isActive: true,
      jobTitle: true, phone: true, departmentId: true, department: true,
    },
  });

  await prisma.activityLog.create({
    data: { action: "user.updated", userId: session.user.id, details: { targetId: params.id } },
  });

  return NextResponse.json(user);
}

export async function DELETE(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  if (session.user.role !== "ADMIN") {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  if (session.user.id === params.id) {
    return NextResponse.json({ error: "Cannot deactivate yourself" }, { status: 400 });
  }

  await prisma.user.update({ where: { id: params.id }, data: { isActive: false } });

  return NextResponse.json({ success: true });
}
