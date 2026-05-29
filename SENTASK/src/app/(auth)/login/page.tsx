"use client";

import { Suspense, useEffect, useState } from "react";
import { getProviders, signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import Link from "next/link";
import { Eye, EyeOff, Lock, Mail, Loader2 } from "lucide-react";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageSkeleton />}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    let active = true;

    getProviders().then((providers) => {
      if (active) setGoogleEnabled(Boolean(providers?.google));
    });

    return () => {
      active = false;
    };
  }, []);

  const verified = searchParams.get("verified") === "1";
  const authError = searchParams.get("error");
  const oauthErrorMessage =
    authError === "AccessDenied"
      ? "Google sign-in was denied. Check that your Seneca Workspace account is in an allowed domain and still active."
      : authError === "Configuration"
        ? "Google sign-in is not configured yet."
        : authError
          ? "Unable to complete Google sign-in. Please try again."
          : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });

      if (result?.error) {
        toast.error("Invalid email or password");
      } else {
        toast.success("Welcome back!");
        window.location.href = "/dashboard";
      }
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSignIn() {
    try {
      setGoogleLoading(true);
      await signIn("google", { callbackUrl: "/dashboard" });
    } catch {
      toast.error("Unable to start Google sign-in.");
      setGoogleLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e3a8a] to-[#1e40af] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-lg">
              <span className="text-[#1e3a8a] font-black text-xl">S</span>
            </div>
            <div className="text-left">
              <h1 className="text-white font-bold text-2xl tracking-tight">SENTASK</h1>
              <p className="text-blue-300 text-sm">Seneca Internal Platform</p>
            </div>
          </div>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="mb-6">
            <h2 className="text-gray-900 font-bold text-xl">Sign in to your account</h2>
            <p className="text-gray-500 text-sm mt-1">Enter your credentials to continue</p>
          </div>

          {verified && (
            <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              Email verified! You can sign in once a Seneca admin approves your account.
            </div>
          )}

          {oauthErrorMessage && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {oauthErrorMessage}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Email address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@seneca.uz"
                  className="w-full pl-10 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <Link
                href="/forgot-password"
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                Forgot password?
              </Link>
            </div>

            <button
              type="submit"
              disabled={loading || googleLoading}
              className="w-full bg-[#1e3a8a] hover:bg-[#1e40af] text-white font-semibold py-2.5 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          {googleEnabled && (
            <>
              <div className="my-6 flex items-center gap-3">
                <div className="h-px flex-1 bg-gray-200" />
                <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
                  Or
                </span>
                <div className="h-px flex-1 bg-gray-200" />
              </div>

              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={loading || googleLoading}
                className="w-full rounded-lg border border-gray-200 bg-white py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {googleLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Redirecting to Google...
                  </>
                ) : (
                  <>
                    <GoogleIcon />
                    Continue with Google
                  </>
                )}
              </button>
            </>
          )}

          <p className="text-center text-sm text-gray-500 mt-6">
            New to SENTASK?{" "}
            <a href="/register" className="text-blue-600 hover:text-blue-700 font-medium">
              Create an account
            </a>
          </p>
        </div>

        <p className="text-center text-blue-300 text-xs mt-6">
          © 2026 Seneca. All rights reserved.
        </p>
      </div>
    </div>
  );
}

function LoginPageSkeleton() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e3a8a] to-[#1e40af] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-lg">
              <span className="text-[#1e3a8a] font-black text-xl">S</span>
            </div>
            <div className="text-left">
              <h1 className="text-white font-bold text-2xl tracking-tight">SENTASK</h1>
              <p className="text-blue-300 text-sm">Seneca Internal Platform</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="mb-6">
            <h2 className="text-gray-900 font-bold text-xl">Sign in to your account</h2>
            <p className="text-gray-500 text-sm mt-1">Loading authentication options...</p>
          </div>

          <div className="space-y-4">
            <div className="h-11 rounded-lg bg-gray-100 animate-pulse" />
            <div className="h-11 rounded-lg bg-gray-100 animate-pulse" />
            <div className="h-11 rounded-lg bg-gray-100 animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M12 10.2v3.9h5.4c-.2 1.3-1.5 3.8-5.4 3.8-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.7 3.2 14.6 2.2 12 2.2A9.8 9.8 0 0 0 2.2 12 9.8 9.8 0 0 0 12 21.8c5.6 0 9.3-3.9 9.3-9.4 0-.6-.1-1.1-.2-1.6H12Z"
      />
      <path
        fill="#34A853"
        d="M2.2 12c0 1.6.4 3.2 1.3 4.5l3.2-2.5A5.9 5.9 0 0 1 6 12c0-.7.1-1.4.4-2L3.2 7.5A9.8 9.8 0 0 0 2.2 12Z"
      />
      <path
        fill="#FBBC05"
        d="M12 21.8c2.7 0 4.9-.9 6.5-2.4l-3.2-2.6c-.9.6-2 1.1-3.3 1.1-2.5 0-4.7-1.7-5.5-4L3.2 16.5A9.8 9.8 0 0 0 12 21.8Z"
      />
      <path
        fill="#4285F4"
        d="M18.5 19.4c1.9-1.8 2.8-4.3 2.8-7 0-.6-.1-1.1-.2-1.6H12v3.9h5.4c-.2 1.1-.8 2.3-1.9 3.1l3 2.3Z"
      />
    </svg>
  );
}
