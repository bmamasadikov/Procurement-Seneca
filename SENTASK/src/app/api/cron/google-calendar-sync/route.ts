import { NextRequest, NextResponse } from "next/server";
import { syncPendingCalendarTasks } from "@/lib/google/calendar";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get("authorization");
  const cronSecret = process.env.CRON_SECRET;

  if (cronSecret && authHeader !== `Bearer ${cronSecret}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const results = await syncPendingCalendarTasks();
    const synced = results.filter((result) => result.status === "SYNCED").length;
    const failed = results.filter((result) => result.status === "FAILED").length;

    return NextResponse.json({
      success: true,
      processed: results.length,
      synced,
      failed,
      results,
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
