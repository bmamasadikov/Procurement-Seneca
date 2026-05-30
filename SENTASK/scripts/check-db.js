/**
 * Run inside Railway container to verify DB state and reset admin password.
 * Usage:  node scripts/check-db.js
 */
const { PrismaClient } = require("@prisma/client");
const bcrypt = require("bcryptjs");

const prisma = new PrismaClient();

async function main() {
  const users = await prisma.user.findMany({
    select: { email: true, role: true, isActive: true, passwordHash: true },
  });

  console.log("\n=== Users in DB ===");
  users.forEach((u) => {
    console.log(
      `  ${u.email}  role=${u.role}  active=${u.isActive}  hash=${u.passwordHash ? "SET" : "NULL"}`
    );
  });

  if (users.length === 0) {
    console.log("  (none — seed has not run yet)");
  }

  // Ensure admin user has correct password hash
  const adminEmail = "admin@seneca.uz";
  const adminPassword = "admin123";
  const hash = await bcrypt.hash(adminPassword, 12);

  const updated = await prisma.user.upsert({
    where: { email: adminEmail },
    update: { passwordHash: hash, isActive: true, role: "ADMIN" },
    create: {
      name: "Admin User",
      email: adminEmail,
      passwordHash: hash,
      role: "ADMIN",
      isActive: true,
      notifyByEmail: true,
      notifyByTelegram: false,
    },
  });

  console.log(`\n✅ Admin user ensured: ${updated.email} (id=${updated.id})`);
}

main()
  .catch((e) => { console.error(e); process.exit(1); })
  .finally(() => prisma.$disconnect());
