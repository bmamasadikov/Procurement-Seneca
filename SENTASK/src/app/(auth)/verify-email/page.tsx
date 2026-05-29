"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");
  const [state, setState] = useState<"loading" | "success" | "error">("loading");

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }

    fetch(`/api/verify-email?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (res.ok) {
          setState("success");
          setTimeout(() => router.push("/login?verified=1"), 2500);
        } else {
          setState("error");
        }
      })
      .catch(() => setState("error"));
  }, [token, router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e3a8a] to-[#1e40af] flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-10 w-full max-w-md text-center">
        {/* Logo */}
        <div className="inline-flex items-center gap-2 mb-8">
          <div className="w-9 h-9 bg-[#1e3a8a] rounded-lg flex items-center justify-center">
            <span className="text-white font-black text-sm">S</span>
          </div>
          <span className="font-bold text-gray-900 text-lg">SENTASK</span>
        </div>

        {state === "loading" && (
          <>
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
            <h2 className="text-xl font-bold text-gray-900 mb-2">Verifying your email…</h2>
            <p className="text-gray-500 text-sm">This will only take a moment.</p>
          </>
        )}

        {state === "success" && (
          <>
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-gray-900 mb-2">Email verified!</h2>
            <p className="text-gray-500 text-sm mb-4">
              Your account is now active. A Seneca admin will approve your access shortly.
            </p>
            <p className="text-xs text-gray-400">Redirecting to sign in…</p>
          </>
        )}

        {state === "error" && (
          <>
            <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-gray-900 mb-2">Link expired or invalid</h2>
            <p className="text-gray-500 text-sm mb-6">
              This verification link may have already been used or has expired (links are valid for 24 hours).
            </p>
            <Link
              href="/register"
              className="inline-block bg-[#1e3a8a] text-white text-sm font-semibold px-6 py-2.5 rounded-lg hover:bg-[#1e40af] transition-colors"
            >
              Register again
            </Link>
            <p className="mt-4">
              <Link href="/login" className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e3a8a] to-[#1e40af] flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-white animate-spin" />
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
