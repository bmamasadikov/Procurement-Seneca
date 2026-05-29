import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";

type Params = { params: { id: string; entryId: string } };

export async function DELETE(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const entry = await prisma.timeEntry.findUnique({ where: { id: params.entryId } });
  if (!entry || entry.taskId !== params.id) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const isOwner = entry.userId === session.user.id;
  const isAdmin = session.user.role === "ADMIN";
  if (!isOwner && !isAdmin) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  await prisma.timeEntry.delete({ where: { id: params.entryId } });
  return NextResponse.json({ success: true });
}
