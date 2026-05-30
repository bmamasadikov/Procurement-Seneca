"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { useSession } from "next-auth/react";
import { cn, getInitials } from "@/lib/utils";
import { canManageTasks, hasFullTaskAccess } from "@/lib/access";
import {
  LayoutDashboard,
  CheckSquare,
  User2,
  Calendar,
  BarChart3,
  Users,
  Settings,
  LogOut,
  Plus,
  ChevronRight,
  Activity,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/tasks", label: "All Tasks", icon: CheckSquare },
  { href: "/my-tasks", label: "My Tasks", icon: User2 },
  { href: "/calendar", label: "Calendar", icon: Calendar },
  { href: "/workload", label: "Workload", icon: Activity, roles: ["ADMIN", "MANAGER"] },
  { href: "/reports", label: "Reports", icon: BarChart3, requiresMasterAccess: true },
  { href: "/team", label: "Team", icon: Users, roles: ["ADMIN", "MANAGER"] },
  { href: "/settings", label: "Settings", icon: Settings, roles: ["ADMIN"] },
  { href: "/profile", label: "My Profile", icon: User2, excludeRoles: ["ADMIN"] },
];

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const role = session?.user?.role;
  const canCreateTasks = canManageTasks(session?.user);
  const canViewReports = hasFullTaskAccess(session?.user);

  const visibleItems = navItems.filter((item) => {
    if (role === "PENDING") return false;
    if (item.requiresMasterAccess) return canViewReports;
    if ((item as any).excludeRoles?.includes(role)) return false;
    return !item.roles || item.roles.includes(role || "");
  });

  return (
    <div className="flex flex-col h-full bg-[#0f172a] text-slate-300">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-slate-700/50">
        <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center flex-shrink-0">
          <span className="text-white font-black text-base">S</span>
        </div>
        <div>
          <p className="text-white font-bold text-base leading-none">SENTASK</p>
          <p className="text-slate-400 text-xs mt-0.5">Seneca Platform</p>
        </div>
      </div>

      {/* Quick action */}
      {canCreateTasks && (
        <div className="px-4 py-3 space-y-2">
          <Link
            href="/tasks/new"
            onClick={onClose}
            className="flex items-center justify-center gap-2 w-full bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold py-2 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Task
          </Link>
          <div className="flex items-center justify-center gap-1.5 text-slate-500 text-xs">
            <span>Quick task:</span>
            <kbd className="bg-slate-800 border border-slate-600 px-1.5 py-0.5 rounded text-[10px] text-slate-400">⌘⇧N</kbd>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {visibleItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group",
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              )}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1">{item.label}</span>
              {isActive && <ChevronRight className="w-3 h-3 opacity-60" />}
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-slate-700/50 p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-blue-700 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {getInitials(session?.user?.name || "U")}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-medium truncate">{session?.user?.name}</p>
            <p className="text-slate-400 text-xs truncate">{session?.user?.role}</p>
          </div>
        </div>
        <Link
          href="/profile"
          onClick={onClose}
          className="flex items-center gap-2 w-full text-slate-400 hover:text-slate-100 text-sm py-1.5 rounded-lg px-2 hover:bg-slate-800 transition-colors mb-1"
        >
          <User2 className="w-4 h-4" />
          My Profile
        </Link>
        <button
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="flex items-center gap-2 w-full text-slate-400 hover:text-red-400 text-sm py-1.5 rounded-lg px-2 hover:bg-red-900/20 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </div>
  );
}
