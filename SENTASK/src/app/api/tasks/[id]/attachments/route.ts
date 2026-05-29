import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canAccessTask } from "@/lib/access";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import { randomBytes } from "crypto";

const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB
const ALLOWED_TYPES = [
  "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-powerpoint",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/plain", "text/csv",
  "application/zip", "application/x-zip-compressed",
];

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });
  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  if (!file) return NextResponse.json({ error: "No file provided" }, { status: 400 });

  if (file.size > MAX_FILE_SIZE) {
    return NextResponse.json({ error: "File too large (max 20 MB)" }, { status: 400 });
  }
  if (!ALLOWED_TYPES.includes(file.type)) {
    return NextResponse.json({ error: "File type not allowed" }, { status: 400 });
  }

  const ext = path.extname(file.name) || "";
  const uniqueName = `${randomBytes(16).toString("hex")}${ext}`;
  const uploadDir = path.join(process.cwd(), "public", "uploads", "tasks", params.id);
  await mkdir(uploadDir, { recursive: true });

  const bytes = await file.arrayBuffer();
  await writeFile(path.join(uploadDir, uniqueName), Buffer.from(bytes));

  const attachment = await prisma.taskAttachment.create({
    data: {
      filename: uniqueName,
      originalName: file.name,
      mimeType: file.type,
      size: file.size,
      url: `/uploads/tasks/${params.id}/${uniqueName}`,
      taskId: params.id,
      uploaderId: session.user.id,
    },
    include: {
      uploader: { select: { id: true, name: true } },
    },
  });

  await prisma.activityLog.create({
    data: {
      action: "attachment.added",
      userId: session.user.id,
      taskId: params.id,
      details: { filename: file.name, size: file.size },
    },
  });

  return NextResponse.json(attachment, { status: 201 });
}

export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const task = await prisma.task.findUnique({ where: { id: params.id } });
  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });
  if (!canAccessTask(session.user, task)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const attachments = await prisma.taskAttachment.findMany({
    where: { taskId: params.id },
    include: { uploader: { select: { id: true, name: true } } },
    orderBy: { createdAt: "desc" },
  });

  return NextResponse.json(attachments);
}
