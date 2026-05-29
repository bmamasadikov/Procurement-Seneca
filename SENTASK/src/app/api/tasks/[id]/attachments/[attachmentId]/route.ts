import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { unlink } from "fs/promises";
import path from "path";

type Params = { params: { id: string; attachmentId: string } };

export async function DELETE(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const attachment = await prisma.taskAttachment.findUnique({
    where: { id: params.attachmentId },
  });
  if (!attachment || attachment.taskId !== params.id) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const isOwner = attachment.uploaderId === session.user.id;
  const isAdmin = session.user.role === "ADMIN";
  if (!isOwner && !isAdmin) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Delete physical file (best-effort)
  try {
    const filePath = path.join(process.cwd(), "public", attachment.url);
    await unlink(filePath);
  } catch {
    // file may already be gone
  }

  await prisma.taskAttachment.delete({ where: { id: params.attachmentId } });
  await prisma.activityLog.create({
    data: {
      action: "attachment.deleted",
      userId: session.user.id,
      taskId: params.id,
      details: { filename: attachment.originalName },
    },
  });

  return NextResponse.json({ success: true });
}
