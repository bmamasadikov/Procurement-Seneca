"use client";

import { signOut, useSession } from "next-auth/react";
import { ShieldCheck } from "lucide-react";

export default function PendingApprovalPage() {
  const { data: session } = useSession();

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e3a8a] to-[#1e40af] flex items-center justify-center p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Pending Approval</h1>
            <p className="text-sm text-gray-500">Your account is connected.</p>
          </div>
        </div>

        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-medium">Your account is waiting for admin approval.</p>
          <p className="mt-2">
            Signed in as <span className="font-semibold">{session?.user?.email}</span>. An admin
            needs to assign your SENTASK role before you can access tasks, reports, and settings.
          </p>
        </div>

        <div className="mt-6 space-y-2 text-sm text-gray-600">
          <p className="font-medium">What happens next:</p>
          <p>1. A Seneca admin will review your account in the Team section.</p>
          <p>2. Once approved you will get access to tasks, reports, and settings.</p>
          <p>3. Sign in again after approval — you will be redirected automatically.</p>
        </div>

        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="mt-8 w-full rounded-lg bg-[#1e3a8a] py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1e40af]"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
