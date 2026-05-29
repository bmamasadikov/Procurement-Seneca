import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { sendPasswordResetEmail } from "@/lib/email";
import { randomBytes } from "crypto";
import { checkRateLimit, getClientIp } from "@/lib/rateLimit";

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);
  if (!checkRateLimit(`forgot:${ip}`, 5, 15 * 60 * 1000)) {
    return NextResponse.json({ error: "Too many requests. Please try again in 15 minutes." }, { status: 429 });
  }

  const { email } = await req.json();
  if (!email) return NextResponse.json({ error: "Email required" }, { status: 400 });

  const user = await prisma.user.findUnique({ where: { email } });

  // Always return success to prevent email enumeration
  if (!user) return NextResponse.json({ success: true });

  const token = randomBytes(32).toString("hex");
  const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour

  await prisma.passwordReset.create({
    data: { token, userId: user.id, expiresAt },
  });

  const resetUrl = `${process.env.APP_URL}/reset-password?token=${token}`;

  try {
    await sendPasswordResetEmail({ to: email, name: user.name, resetUrl });
  } catch (err) {
    console.error("Password reset email failed:", err);
  }

  return NextResponse.json({ success: true });
}
