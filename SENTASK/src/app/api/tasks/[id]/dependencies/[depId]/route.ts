import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { prisma } from "@/lib/prisma";
import { canManageTasks } from "@/lib/access";

type Params = { params: { id: string; depId: string } };

export async function DELETE(req: NextRequest, { params }: Params) {
  const session = await auth();
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!canManageTasks(session.user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  await prisma.taskDependency.deleteMany({
    where: { taskId: params.id, dependsOnId: params.depId },
  });

  return NextResponse.json({ success: true });
}
