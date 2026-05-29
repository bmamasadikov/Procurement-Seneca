#!/usr/bin/env node

const { randomBytes } = require("crypto");
const { PrismaClient } = require("@prisma/client");

const prisma = new PrismaClient();

function normalizeEmails(rawEmails) {
  return rawEmails
    .map((email) => String(email || "").trim().toLowerCase())
    .filter(Boolean);
}

async function main() {
  const rawEmails = process.argv.slice(2);
  if (!rawEmails.length) {
    console.error("Usage: node scripts/generate-password-setup-links.js <email1> <email2> ...");
    process.exit(1);
  }

  const emails = normalizeEmails(rawEmails);
  const baseUrl = (process.env.SETUP_LINK_BASE_URL || process.env.APP_URL || "").replace(/\/$/, "");
  const expiresHours = Number(process.env.SETUP_LINK_EXPIRES_HOURS || 72);
  const expiresAt = new Date(Date.now() + expiresHours * 60 * 60 * 1000);
  const now = new Date();

  const results = [];

  for (const email of emails) {
    const user = await prisma.user.findUnique({
      where: { email },
      select: { id: true, email: true, name: true, isActive: true },
    });

    if (!user) {
      results.push({ email, status: "not_found" });
      continue;
    }

    const token = randomBytes(32).toString("hex");

    await prisma.$transaction([
      prisma.passwordReset.updateMany({
        where: { userId: user.id, usedAt: null },
        data: { usedAt: now },
      }),
      prisma.passwordReset.create({
        data: { token, userId: user.id, expiresAt },
      }),
      prisma.activityLog.create({
        data: {
          action: "user.password_setup_link_generated",
          userId: user.id,
          details: { generatedFor: email, expiresAt: expiresAt.toISOString() },
        },
      }),
    ]);

    const linkPath = `/reset-password?token=${token}`;
    const resetUrl = baseUrl ? `${baseUrl}${linkPath}` : linkPath;

    results.push({
      email: user.email,
      name: user.name,
      isActive: user.isActive,
      status: "ready",
      expiresAt: expiresAt.toISOString(),
      resetUrl,
    });
  }

  console.log(JSON.stringify({ baseUrl, expiresHours, results }, null, 2));
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
