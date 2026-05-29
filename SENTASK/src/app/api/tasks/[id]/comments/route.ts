import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { notifyCommentAdded, notifyMentioned } from "@/lib/services/notifications";
import { canAccessTask } from "@/lib/access";
import { z } from "zod";

const commentSchema = z.object({ content: z.string().min(1).max(2000) });

const COMMENTS_PAGE_SIZE = 50;

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const cursor = req.nextUrl.searchParams.get("cursor");

  const comments = await prisma.taskComment.findMany({
    where: { taskId: params.id },
    include: { author: { select: { id: true, name: true, email: true, avatarUrl: true } } },
    orderBy: { createdAt: "asc" },
    take: COMMENTS_PAGE_SIZE + 1,
    ...(cursor ? { cursor: { id: cursor }, skip: 1 } : {}),
  });

  const hasMore = comments.length > COMMENTS_PAGE_SIZE;
  const page = hasMore ? comments.slice(0, COMMENTS_PAGE_SIZE) : comments;
  const nextCursor = hasMore ? page[page.length - 1].id : null;

  return NextResponse.json({ comments: page, nextCursor, hasMore });
}

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });

  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = commentSchema.safeParse(body);
  if (!parsed.success) return NextResponse.json({ error: "Validation failed" }, { status: 422 });

  const comment = await prisma.taskComment.create({
    data: { content: parsed.data.content, taskId: params.id, authorId: session.user.id },
    include: { author: { select: { id: true, name: true, email: true, avatarUrl: true } } },
  });

  await prisma.activityLog.create({
    data: {
      action: "comment.added",
      userId: session.user.id,
      taskId: params.id,
      details: { commentId: comment.id, preview: parsed.data.content.slice(0, 100) },
    },
  });

  await notifyCommentAdded({
    taskId: params.id,
    commenterId: session.user.id,
    commentContent: parsed.data.content,
  });

  // Parse @mentions: match @FirstName or @First_Last patterns
  const mentionRegex = /@([\w.]+)/g;
  const mentionMatches = [...parsed.data.content.matchAll(mentionRegex)];
  if (mentionMatches.length > 0) {
    const mentionNames = mentionMatches.map((m) => m[1].replace(/_/g, " ").toLowerCase());
    const allUsers = await prisma.user.findMany({
      where: { isActive: true },
      select: { id: true, name: true },
    });
    const mentionedUserIds = allUsers
      .filter((u) => mentionNames.some((m) => u.name.toLowerCase().includes(m)))
      .map((u) => u.id)
      .filter((id) => id !== session.user.id);

    for (const userId of mentionedUserIds) {
      await notifyMentioned({
        taskId: params.id,
        commentId: comment.id,
        mentionedUserId: userId,
        mentionedByName: session.user.name || session.user.email || "Someone",
        commentContent: parsed.data.content,
      });
    }
  }

  return NextResponse.json(comment, { status: 201 });
}
