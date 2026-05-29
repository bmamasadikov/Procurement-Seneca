"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Task } from "@/types";
import { TaskTable } from "@/components/tasks/TaskTable";
import { ListTodo, Clock, AlertTriangle, CheckCircle2, RefreshCw, CalendarDays } from "lucide-react";

type Tab = "all" | "today" | "week" | "overdue" | "done" | "recurring";

export default function MyTasksPage() {
  const [tab, setTab] = useState<Tab>("all");

  const { data: allData, isLoading } = useQuery({
    queryKey: ["tasks", "my-all"],
    queryFn: async () => {
      const res = await fetch("/api/tasks?myTasks=true&pageSize=100");
      return res.json() as Promise<{ data: Task[] }>;
    },
  });

  const all = allData?.data || [];
  const now = new Date();

  function setHours(d: Date) {
    const copy = new Date(d);
    copy.setHours(0, 0, 0, 0);
    return copy;
  }

  const today = all.filter((t) => {
    if (!t.dueDate) return false;
    const due = setHours(new Date(t.dueDate));
    const todayDate = setHours(now);
    return due.getTime() === todayDate.getTime() && t.status !== "DONE";
  });

  const overdue = all.filter((t) => {
    if (!t.dueDate || t.status === "DONE") return false;
    return new Date(t.dueDate) < now && !today.find((td) => td.id === t.id);
  });

  const week = all.filter((t) => {
    if (!t.dueDate || t.status === "DONE") return false;
    const dueMidnight = setHours(new Date(t.dueDate));
    const todayMidnight = setHours(now);
    const weekFromNow = setHours(new Date(now.getTime() + 7 * 86400000));
    return dueMidnight > todayMidnight && dueMidnight <= weekFromNow;
  });

  const done = all.filter((t) => t.status === "DONE");
  const recurring = all.filter((t) => t.repeatType !== "NONE");

  const TABS: { key: Tab; label: string; icon: typeof Clock; count: number; color: string }[] = [
    { key: "all", label: "All", icon: ListTodo, count: all.length, color: "blue" },
    { key: "today", label: "Due Today", icon: Clock, count: today.length, color: "amber" },
    { key: "week", label: "This Week", icon: CalendarDays, count: week.length, color: "orange" },
    { key: "overdue", label: "Overdue", icon: AlertTriangle, count: overdue.length, color: "red" },
    { key: "done", label: "Completed", icon: CheckCircle2, count: done.length, color: "green" },
    { key: "recurring", label: "Recurring", icon: RefreshCw, count: recurring.length, color: "purple" },
  ];

  const tabColorMap: Record<string, string> = {
    blue: "border-blue-500 text-blue-600",
    amber: "border-amber-500 text-amber-600",
    orange: "border-orange-500 text-orange-600",
    red: "border-red-500 text-red-600",
    green: "border-green-500 text-green-600",
    purple: "border-purple-500 text-purple-600",
  };

  const currentTasks = {
    all,
    today,
    week,
    overdue,
    done,
    recurring,
  }[tab];

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Tabs */}
      <div className="flex gap-1 overflow-x-auto border-b border-gray-100 pb-0">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                active
                  ? `${tabColorMap[t.color]} border-b-2`
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
              {t.count > 0 && (
                <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold ${
                  active
                    ? t.color === "red" ? "bg-red-100 text-red-600" :
                      t.color === "amber" ? "bg-amber-100 text-amber-600" :
                      t.color === "orange" ? "bg-orange-100 text-orange-600" :
                      t.color === "green" ? "bg-green-100 text-green-600" :
                      t.color === "purple" ? "bg-purple-100 text-purple-600" :
                      "bg-blue-100 text-blue-600"
                    : "bg-gray-100 text-gray-500"
                }`}>
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <TaskTable tasks={currentTasks} isLoading={isLoading} />
    </div>
  );
}
