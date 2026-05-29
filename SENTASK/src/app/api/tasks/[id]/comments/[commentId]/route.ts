import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { z } from "zod";

const editSchema = z.object({ content: z.string().min(1).max(2000) });

type Params = { params: { id: string; commentId: string } };

export async function PATCH(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const comment = await prisma.taskComment.findUnique({
    where: { id: params.commentId },
  });
  if (!comment || comment.taskId !== params.id) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  if (comment.authorId !== session.user.id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = editSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: "Validation failed" }, { status: 422 });

  const updated = await prisma.taskComment.update({
    where: { id: params.commentId },
    data: { content: parsed.data.content },
    include: { author: { select: { id: true, name: true, email: true, avatarUrl: true } } },
  });

  return NextResponse.json(updated);
}

export async function DELETE(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const comment = await prisma.taskComment.findUnique({
    where: { id: params.commentId },
  });
  if (!comment || comment.taskId !== params.id) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const isOwner = comment.authorId === session.user.id;
  const isAdmin = session.user.role === "ADMIN";
  if (!isOwner && !isAdmin) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  await prisma.taskComment.delete({ where: { id: params.commentId } });
  await prisma.activityLog.create({
    data: {
      action: "comment.deleted",
      userId: session.user.id,
      taskId: params.id,
    },
  });

  return NextResponse.json({ success: true });
}
