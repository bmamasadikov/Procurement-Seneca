import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";

export default auth((req) => {
  const session = req.auth;
  const isLoggedIn = Boolean(session);
  const { pathname } = req.nextUrl;
  const role = session?.user?.role;

  const publicApiPaths = ["/api/forgot-password", "/api/reset-password", "/api/register", "/api/verify-email"];
  const publicPaths = ["/login", "/forgot-password", "/reset-password", "/pending-approval", "/register", "/verify-email"];
  const isPublic = publicPaths.some((p) => pathname.startsWith(p));
  const isPublicApi = publicApiPaths.some((p) => pathname.startsWith(p));
  const isPendingUser = role === "PENDING";

  if (!isLoggedIn && !isPublic && !pathname.startsWith("/api/auth")) {
    if (pathname.startsWith("/api/")) {
      if (isPublicApi) return NextResponse.next();
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const redirectUrl = new URL("/login", req.url);
    redirectUrl.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(redirectUrl);
  }

  if (isLoggedIn && isPendingUser) {
    if (pathname.startsWith("/api/") && !pathname.startsWith("/api/auth")) {
      return new NextResponse(JSON.stringify({ error: "Pending approval" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      });
    }
    if (!pathname.startsWith("/pending-approval") && !pathname.startsWith("/api/auth")) {
      return NextResponse.redirect(new URL("/pending-approval", req.url));
    }
  }

  if (isLoggedIn && pathname.startsWith("/pending-approval") && !isPendingUser) {
    return NextResponse.redirect(new URL("/dashboard", req.url));
  }

  if (isLoggedIn && isPublic) {
    return NextResponse.redirect(
      new URL(isPendingUser ? "/pending-approval" : "/dashboard", req.url)
    );
  }

  // Settings page and settings API are ADMIN-only
  if (isLoggedIn && !isPendingUser && role !== "ADMIN") {
    if (pathname.startsWith("/settings")) {
      return NextResponse.redirect(new URL("/dashboard", req.url));
    }
    if (pathname.startsWith("/api/settings/")) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  return NextResponse.next();
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sw.js|manifest.webmanifest|public).*)"],
};
