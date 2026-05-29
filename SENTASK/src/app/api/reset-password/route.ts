import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import bcrypt from "bcryptjs";
import { z } from "zod";
import { checkRateLimit, getClientIp } from "@/lib/rateLimit";

const resetPasswordSchema = z.object({
  token: z.string().min(32),
  password: z.string().min(8).max(128),
});

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);
  if (!checkRateLimit(`reset:${ip}`, 10, 60 * 60 * 1000)) {
    return NextResponse.json({ error: "Too many requests. Please try again later." }, { status: 429 });
  }

  const parsed = resetPasswordSchema.safeParse(await req.json());
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid request" }, { status: 400 });
  }

  const { token, password } = parsed.data;
  const now = new Date();

  const resetRequest = await prisma.passwordReset.findFirst({
    where: {
      token,
      usedAt: null,
      expiresAt: { gt: now },
    },
    select: {
      id: true,
      userId: true,
    },
  });

  if (!resetRequest) {
    return NextResponse.json({ error: "Invalid or expired reset link" }, { status: 400 });
  }

  const passwordHash = await bcrypt.hash(password, 12);

  await prisma.$transaction([
    prisma.user.update({
      where: { id: resetRequest.userId },
      data: {
        passwordHash,
        isActive: true,
      },
    }),
    prisma.passwordReset.update({
      where: { id: resetRequest.id },
      data: { usedAt: now },
    }),
    prisma.passwordReset.updateMany({
      where: {
        userId: resetRequest.userId,
        usedAt: null,
        id: { not: resetRequest.id },
      },
      data: { usedAt: now },
    }),
    prisma.activityLog.create({
      data: {
        action: "user.password_reset_completed",
        userId: resetRequest.userId,
        details: { method: "email_link" },
      },
    }),
  ]);

  return NextResponse.json({ success: true });
}
