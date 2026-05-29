"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Menu, X, Check } from "lucide-react";
import { Notification } from "@/types";
import { formatRelative } from "@/lib/utils";
import Link from "next/link";

interface HeaderProps {
  title: string;
  onMenuClick: () => void;
}

export function Header({ title, onMenuClick }: HeaderProps) {
  const [notifOpen, setNotifOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const res = await fetch("/api/notifications?limit=10");
      return res.json() as Promise<{ notifications: Notification[]; unreadCount: number }>;
    },
    refetchInterval: 30_000,
  });

  const markAllRead = useMutation({
    mutationFn: async () => {
      await fetch("/api/notifications?markAll=true", { method: "PATCH" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  async function markOneRead(id: string) {
    await fetch("/api/notifications", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [id] }),
    });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  const unreadCount = data?.unreadCount || 0;
  const notifications = data?.notifications || [];

  return (
    <header className="h-14 bg-white border-b border-gray-100 flex items-center px-4 gap-4 flex-shrink-0">
      <button
        onClick={onMenuClick}
        className="lg:hidden text-gray-500 hover:text-gray-700 transition-colors"
      >
        <Menu className="w-5 h-5" />
      </button>

      <h1 className="font-semibold text-gray-900 text-base flex-1">{title}</h1>

      {/* Notifications */}
      <div className="relative">
        <button
          onClick={() => setNotifOpen(!notifOpen)}
          className="relative w-9 h-9 flex items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
        >
          <Bell className="w-5 h-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>

        {notifOpen && (
          <>
            <div
              className="fixed inset-0 z-30"
              onClick={() => setNotifOpen(false)}
            />
            <div className="absolute right-0 top-11 w-80 bg-white rounded-xl shadow-xl border border-gray-100 z-40 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                <span className="font-semibold text-gray-900 text-sm">Notifications</span>
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <button
                      onClick={() => markAllRead.mutate()}
                      className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 font-medium"
                    >
                      <Check className="w-3 h-3" />
                      Mark all read
                    </button>
                  )}
                  <button onClick={() => setNotifOpen(false)} className="text-gray-400 hover:text-gray-600">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="max-h-80 overflow-y-auto divide-y divide-gray-50">
                {notifications.length === 0 ? (
                  <div className="py-10 text-center text-gray-400 text-sm flex flex-col items-center gap-2">
                    <Bell className="w-8 h-8 text-gray-200" />
                    <span>No notifications yet</span>
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className={`px-4 py-3 hover:bg-gray-50 transition-colors ${!n.isRead ? "bg-blue-50/40" : ""}`}
                      onClick={() => { if (!n.isRead) markOneRead(n.id); }}
                    >
                      {n.taskId ? (
                        <Link
                          href={`/tasks/${n.taskId}`}
                          onClick={() => setNotifOpen(false)}
                          className="block"
                        >
                          <NotificationItem n={n} />
                        </Link>
                      ) : (
                        <NotificationItem n={n} />
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </header>
  );
}

function NotificationItem({ n }: { n: Notification }) {
  return (
    <>
      <div className="flex items-start gap-2">
        <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${!n.isRead ? "bg-blue-500" : "bg-gray-200"}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{n.title}</p>
          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{n.message}</p>
          <p className="text-xs text-gray-400 mt-1">{formatRelative(n.createdAt)}</p>
        </div>
      </div>
    </>
  );
}
