import NextAuth, { type DefaultSession } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import { prisma } from "@/lib/prisma";
import bcrypt from "bcryptjs";
import { Role } from "@/types";
import { getGoogleWorkspaceSettings, isAllowedGoogleDomain } from "@/lib/settings";
import { hasFullTaskAccess } from "@/lib/access";

type AppSessionUser = {
  id: string;
  name: string;
  email: string;
  googleEmail?: string | null;
  role: Role;
  isMasterAccount?: boolean;
  authProvider?: "CREDENTIALS" | "GOOGLE";
  departmentId?: string | null;
  avatarUrl?: string | null;
  jobTitle?: string | null;
};

type AppLoginUser = AppSessionUser & {
  isActive: boolean;
  passwordHash?: string | null;
  googleId?: string | null;
};

function toSessionUser(user: AppLoginUser | AppSessionUser): AppSessionUser {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    googleEmail: user.googleEmail,
    role: user.role,
    isMasterAccount: hasFullTaskAccess(user),
    authProvider: user.authProvider,
    departmentId: user.departmentId,
    avatarUrl: user.avatarUrl,
    jobTitle: user.jobTitle,
  };
}

async function getWorkspaceUserByEmail(email: string) {
  const user = await prisma.user.findUnique({
    where: { email },
    select: {
      id: true,
      name: true,
      email: true,
      googleEmail: true,
      googleId: true,
      passwordHash: true,
      role: true,
      authProvider: true,
      isActive: true,
      departmentId: true,
      avatarUrl: true,
      jobTitle: true,
    },
  });

  if (!user) return null;
  return user as AppLoginUser;
}

async function recordSuccessfulLogin(
  user: AppSessionUser,
  avatarUrl?: string | null,
  provider: "credentials" | "google" = "credentials"
) {
  await prisma.user.update({
    where: { id: user.id },
    data: {
      lastLoginAt: new Date(),
      ...(avatarUrl && avatarUrl !== user.avatarUrl ? { avatarUrl } : {}),
    },
  });

  await prisma.activityLog.create({
    data: {
      action: "user.login",
      userId: user.id,
      details: { email: user.email, provider },
    },
  });
}

const googleEnabled = Boolean(
  process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET
);

async function resolveGoogleUser(params: {
  email: string;
  googleId?: string | null;
  name?: string | null;
  image?: string | null;
  domain?: string | null;
  accessToken?: string | null;
  refreshToken?: string | null;
  tokenExpiry?: number | null;
}) {
  const settings = await getGoogleWorkspaceSettings();
  const email = params.email.trim().toLowerCase();
  const domain = params.domain?.trim().toLowerCase() || null;

  // If the user has a hosted domain, check it's an allowed workspace domain
  const isDomainAllowed = domain ? await isAllowedGoogleDomain(domain) : false;

  // Block unrecognised workspace domains (e.g. competitor's GSuite)
  // but allow personal Gmail (no domain) and allowed workspace domains
  if (domain && !isDomainAllowed) {
    return null;
  }

  let user = await getWorkspaceUserByEmail(email);

  if (!user) {
    // Personal Gmail users always go through approval; workspace users follow settings
    const requireApproval = domain ? settings.adminApprovalRequired : true;

    if (domain && !settings.autoProvisionUsers) {
      return null;
    }

    user = (await prisma.user.create({
      data: {
        name: params.name?.trim() || email,
        email,
        googleEmail: email,
        googleId: params.googleId || undefined,
        googleDomain: domain || undefined,
        authProvider: "GOOGLE",
        role: requireApproval ? "PENDING" : "STAFF",
        isActive: true,
        avatarUrl: params.image || undefined,
        notifyByEmail: true,
        googleAccessToken: params.accessToken || undefined,
        googleRefreshToken: params.refreshToken || undefined,
        googleTokenExpiry: params.tokenExpiry ? new Date(params.tokenExpiry * 1000) : undefined,
      },
      select: {
        id: true, name: true, email: true, googleEmail: true, googleId: true,
        passwordHash: true, role: true, authProvider: true, isActive: true,
        departmentId: true, avatarUrl: true, jobTitle: true,
      },
    })) as AppLoginUser;
  } else {
    const tokenUpdates: Record<string, unknown> = {};
    if (params.accessToken) tokenUpdates.googleAccessToken = params.accessToken;
    if (params.refreshToken) tokenUpdates.googleRefreshToken = params.refreshToken;
    if (params.tokenExpiry) tokenUpdates.googleTokenExpiry = new Date(params.tokenExpiry * 1000);

    user = (await prisma.user.update({
      where: { id: user.id },
      data: {
        name: params.name?.trim() || user.name,
        googleEmail: email,
        googleId: params.googleId || user.googleId,
        googleDomain: domain || undefined,
        avatarUrl: params.image || user.avatarUrl || undefined,
        authProvider: "GOOGLE",
        ...tokenUpdates,
      },
      select: {
        id: true, name: true, email: true, googleEmail: true, googleId: true,
        passwordHash: true, role: true, authProvider: true, isActive: true,
        departmentId: true, avatarUrl: true, jobTitle: true,
      },
    })) as AppLoginUser;
  }

  if (!user.isActive) return null;
  return user;
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        const email = String(credentials.email).trim().toLowerCase();
        const user = await getWorkspaceUserByEmail(email);
        if (!user || !user.isActive || user.role === "PENDING" || !user.passwordHash) return null;

        const isValid = await bcrypt.compare(
          credentials.password as string,
          user.passwordHash
        );

        if (!isValid) return null;

        const sessionUser = toSessionUser(user);
        await recordSuccessfulLogin(sessionUser);
        return sessionUser;
      },
    }),
    ...(googleEnabled
      ? [
          GoogleProvider({
            clientId: process.env.GOOGLE_CLIENT_ID!,
            clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
            authorization: {
              params: {
                prompt: "select_account consent",
                access_type: "offline",
                scope: "openid email profile https://www.googleapis.com/auth/calendar.events",
              },
            },
          }),
        ]
      : []),
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider !== "google") return true;

      const email = user.email?.trim().toLowerCase();
      if (!email) return false;

      const emailVerified =
        typeof (profile as { email_verified?: unknown } | undefined)?.email_verified === "boolean"
          ? (profile as { email_verified: boolean }).email_verified
          : false;

      // Reject unverified Google accounts
      if (!emailVerified) return false;

      const hostedDomain =
        typeof (profile as { hd?: unknown } | undefined)?.hd === "string"
          ? ((profile as { hd: string }).hd || "").toLowerCase()
          : null;

      const resolvedUser = await resolveGoogleUser({
        email,
        googleId:
          typeof profile?.sub === "string"
            ? profile.sub
            : typeof account.providerAccountId === "string"
              ? account.providerAccountId
              : null,
        name: user.name,
        image: user.image,
        domain: hostedDomain,
        accessToken: account.access_token ?? null,
        refreshToken: account.refresh_token ?? null,
        tokenExpiry: typeof account.expires_at === "number" ? account.expires_at : null,
      });

      if (!resolvedUser) return false;

      await recordSuccessfulLogin(toSessionUser(resolvedUser), user.image, "google");
      return true;
    },
    async jwt({ token, user, account }) {
      const tok = token as typeof token & {
        id?: string;
        googleEmail?: string | null;
        role?: Role;
        isMasterAccount?: boolean;
        authProvider?: "CREDENTIALS" | "GOOGLE";
        departmentId?: string | null;
        avatarUrl?: string | null;
        jobTitle?: string | null;
      };

      if (user && account?.provider === "credentials") {
        tok.id = user.id;
        tok.googleEmail = user.googleEmail;
        tok.role = user.role;
        tok.isMasterAccount = user.isMasterAccount;
        tok.authProvider = user.authProvider;
        tok.departmentId = user.departmentId;
        tok.avatarUrl = user.avatarUrl;
        tok.jobTitle = user.jobTitle;
      }

      if ((account?.provider === "google" || (!tok.id && tok.email)) && tok.email) {
        const dbUser = await getWorkspaceUserByEmail(tok.email.toLowerCase() as string);
        if (dbUser && dbUser.isActive) {
          const sessionUser = toSessionUser(dbUser);
          tok.id = sessionUser.id;
          tok.googleEmail = sessionUser.googleEmail;
          tok.role = sessionUser.role;
          tok.isMasterAccount = sessionUser.isMasterAccount;
          tok.authProvider = sessionUser.authProvider;
          tok.departmentId = sessionUser.departmentId;
          tok.avatarUrl = sessionUser.avatarUrl;
          tok.jobTitle = sessionUser.jobTitle;
          tok.name = sessionUser.name;
          tok.email = sessionUser.email;
        }
      }

      return tok;
    },
    async session({ session, token }) {
      if (token) {
        const tok = token as typeof token & {
          id?: string;
          googleEmail?: string | null;
          role?: Role;
          isMasterAccount?: boolean;
          authProvider?: "CREDENTIALS" | "GOOGLE";
          departmentId?: string | null;
          avatarUrl?: string | null;
          jobTitle?: string | null;
        };
        session.user.id = tok.id as string;
        session.user.googleEmail = tok.googleEmail as string | undefined;
        session.user.role = tok.role as Role;
        session.user.isMasterAccount = Boolean(tok.isMasterAccount);
        session.user.authProvider = tok.authProvider as "CREDENTIALS" | "GOOGLE" | undefined;
        session.user.departmentId = tok.departmentId as string;
        session.user.avatarUrl = tok.avatarUrl as string;
        session.user.jobTitle = tok.jobTitle as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
  session: { strategy: "jwt" },
  secret: process.env.NEXTAUTH_SECRET,
});

declare module "next-auth" {
  interface User {
    googleEmail?: string | null;
    role: Role;
    isMasterAccount?: boolean;
    authProvider?: "CREDENTIALS" | "GOOGLE";
    departmentId?: string | null;
    avatarUrl?: string | null;
    jobTitle?: string | null;
  }

  interface Session {
    user: {
      id: string;
      googleEmail?: string;
      role: Role;
      isMasterAccount?: boolean;
      authProvider?: "CREDENTIALS" | "GOOGLE";
      departmentId?: string;
      avatarUrl?: string;
      jobTitle?: string;
    } & DefaultSession["user"];
  }
}

