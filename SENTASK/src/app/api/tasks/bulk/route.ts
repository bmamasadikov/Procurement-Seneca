import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canManageTasks, hasFullTaskAccess } from "@/lib/access";
import { z } from "zod";

const bulkSchema = z.discriminatedUnion("action", [
  z.object({ action: z.literal("status"), ids: z.array(z.string()).min(1), value: z.enum(["BACKLOG", "TODO", "IN_PROGRESS", "WAITING", "DONE"]) }),
  z.object({ action: z.literal("priority"), ids: z.array(z.string()).min(1), value: z.enum(["CRITICAL", "HIGH", "MEDIUM", "LOW"]) }),
  z.object({ action: z.literal("assignee"), ids: z.array(z.string()).min(1), value: z.string().nullable() }),
  z.object({ action: z.literal("archive"), ids: z.array(z.string()).min(1) }),
]);

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!canManageTasks(session.user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = bulkSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Validation failed", details: parsed.error.flatten() }, { status: 422 });
  }

  const { action, ids } = parsed.data;

  // Limit to tasks the user can actually see
  const where = hasFullTaskAccess(session.user)
    ? { id: { in: ids }, isArchived: false }
    : { id: { in: ids }, isArchived: false, OR: [{ assigneeId: session.user.id }, { creatorId: session.user.id }] };

  let updateData: Record<string, any> = {};

  if (action === "status") {
    updateData = {
      status: parsed.data.value,
      ...(parsed.data.value === "DONE" ? { completedAt: new Date(), isOverdue: false } : {}),
    };
  } else if (action === "priority") {
    updateData = { priority: parsed.data.value };
  } else if (action === "assignee") {
    updateData = { assigneeId: parsed.data.value };
  } else if (action === "archive") {
    updateData = { isArchived: true };
  }

  const result = await prisma.task.updateMany({ where, data: updateData });

  await prisma.activityLog.createMany({
    data: ids.map((taskId) => ({
      action: `task.bulk_${action}`,
      userId: session.user.id,
      taskId,
      details: { action, value: (parsed.data as any).value ?? null },
    })),
  });

  return NextResponse.json({ updated: result.count });
}
