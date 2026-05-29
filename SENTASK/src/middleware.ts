import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

export default async function middleware(req: NextRequest) {
  const token = await getToken({
    req,
    secret: process.env.NEXTAUTH_SECRET,
  });
  const isLoggedIn = Boolean(token);
  const { pathname } = req.nextUrl;
  const role = typeof token?.role === "string" ? token.role : undefined;
  const publicApiPaths = ["/api/forgot-password", "/api/reset-password", "/api/register", "/api/verify-email"];

  const publicPaths = ["/login", "/forgot-password", "/reset-password", "/pending-approval", "/register", "/verify-email"];
  const isPublic = publicPaths.some((p) => pathname.startsWith(p));
  const isPublicApi = publicApiPaths.some((p) => pathname.startsWith(p));
  const isPendingUser = role === "PENDING";

  if (!isLoggedIn && !isPublic && !pathname.startsWith("/api/auth")) {
    if (pathname.startsWith("/api/")) {
      if (isPublicApi) {
        return NextResponse.next();
      }
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

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|public).*)"],
};
