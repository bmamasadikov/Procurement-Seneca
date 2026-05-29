"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { StatsCard } from "@/components/dashboard/StatsCard";
import {
  CheckSquare, Clock, AlertTriangle, CheckCircle2,
  Hourglass, ListTodo, BarChart3, Calendar, TrendingUp, PartyPopper, CalendarClock, Sunrise,
} from "lucide-react";
import { Task } from "@/types";
import { formatDate, isOverdue, isDueToday, PRIORITY_CONFIG, STATUS_CONFIG } from "@/lib/utils";
import { hasFullTaskAccess } from "@/lib/access";
import Link from "next/link";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from "recharts";

const STATUS_COLORS = {
  BACKLOG: "#94a3b8",
  TODO: "#3b82f6",
  IN_PROGRESS: "#f59e0b",
  WAITING: "#8b5cf6",
  DONE: "#10b981",
};

export default function DashboardPage() {
  const { data: session } = useSession();
  const canViewGlobalTaskData = hasFullTaskAccess(session?.user);

  const { data: reports, isLoading } = useQuery({
    queryKey: ["reports"],
    queryFn: async () => {
      const res = await fetch("/api/reports");
      return res.json();
    },
    enabled: canViewGlobalTaskData,
  });

  const { data: myTasksData } = useQuery({
    queryKey: ["tasks", "my"],
    queryFn: async () => {
      const res = await fetch("/api/tasks?myTasks=true&pageSize=5");
      return res.json() as Promise<{ data: Task[]; total: number }>;
    },
  });

  const { data: myStatsData } = useQuery({
    queryKey: ["tasks", "my-stats"],
    queryFn: async () => {
      const res = await fetch("/api/tasks?myTasks=true&pageSize=200");
      return res.json() as Promise<{ data: Task[]; total: number }>;
    },
    enabled: !canViewGlobalTaskData,
  });

  const { data: overdueData } = useQuery({
    queryKey: ["tasks", "overdue"],
    queryFn: async () => {
      const res = await fetch("/api/tasks?overdue=true&pageSize=5");
      return res.json() as Promise<{ data: Task[]; total: number }>;
    },
    enabled: canViewGlobalTaskData,
  });

  const { data: dueTodayData } = useQuery({
    queryKey: ["tasks", "due-today"],
    queryFn: async () => {
      const res = await fetch("/api/tasks?dueToday=true&pageSize=5");
      return res.json() as Promise<{ data: Task[]; total: number }>;
    },
    enabled: canViewGlobalTaskData,
  });

  const stats = reports?.stats;
  const myTasks = myTasksData?.data || [];
  const overdueTasks = overdueData?.data || [];
  const dueTodayTasks = dueTodayData?.data || [];

  const myAllTasks = myStatsData?.data || [];
  const now = new Date();
  const myStats = !canViewGlobalTaskData ? {
    open: myAllTasks.filter((t) => t.status !== "DONE").length,
    done: myAllTasks.filter((t) => t.status === "DONE").length,
    overdue: myAllTasks.filter((t) => t.dueDate && t.status !== "DONE" && new Date(t.dueDate) < now).length,
    inProgress: myAllTasks.filter((t) => t.status === "IN_PROGRESS").length,
    completionRate: myAllTasks.length > 0
      ? Math.round((myAllTasks.filter((t) => t.status === "DONE").length / myAllTasks.length) * 100)
      : 0,
  } : null;

  const pieData = stats
    ? [
        { name: "Backlog", value: stats.backlog, color: STATUS_COLORS.BACKLOG },
        { name: "To Do", value: stats.todo, color: STATUS_COLORS.TODO },
        { name: "In Progress", value: stats.inProgress, color: STATUS_COLORS.IN_PROGRESS },
        { name: "Waiting", value: stats.waiting, color: STATUS_COLORS.WAITING },
        { name: "Done", value: stats.done, color: STATUS_COLORS.DONE },
      ].filter((d) => d.value > 0)
    : [];

  const employeeData = (reports?.employeeStats || []).slice(0, 8).map((e: any) => ({
    name: e.name.split(" ")[0],
    Done: e.done,
    "In Progress": e.inProgress,
    Overdue: e.overdue,
  }));

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Welcome */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-blue-50 rounded-xl flex items-center justify-center flex-shrink-0">
          <Sunrise className="w-5 h-5 text-blue-500" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">
            Good {getGreeting()}, {session?.user?.name?.split(" ")[0]}
          </h2>
          <p className="text-gray-500 text-sm mt-0.5">
            Here&apos;s what&apos;s happening with your tasks today.
          </p>
        </div>
      </div>

      {/* Personal stats for STAFF */}
      {!canViewGlobalTaskData && myStats && myAllTasks.length === 0 && (
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-6 flex items-center gap-4">
          <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <CheckCircle2 className="w-6 h-6 text-blue-500" />
          </div>
          <div>
            <p className="font-semibold text-gray-900">You have no tasks yet</p>
            <p className="text-sm text-gray-500 mt-0.5">Your manager will assign tasks to you — check back soon.</p>
          </div>
        </div>
      )}

      {!canViewGlobalTaskData && myStats && myAllTasks.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatsCard label="My Open Tasks" value={myStats.open} icon={ListTodo} color="blue" />
          <StatsCard label="In Progress" value={myStats.inProgress} icon={Clock} color="yellow" />
          <StatsCard label="Completed" value={myStats.done} icon={CheckCircle2} color="green" />
          <StatsCard label="Overdue" value={myStats.overdue} icon={AlertTriangle} color="red" />
          <StatsCard label="My Completion" value={myStats.completionRate} icon={TrendingUp} color="green" suffix="%" />
        </div>
      )}

      {/* Stats grid skeleton */}
      {canViewGlobalTaskData && isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 p-5 flex items-start gap-4 animate-pulse">
              <div className="w-11 h-11 rounded-xl bg-gray-100 flex-shrink-0" />
              <div className="flex-1">
                <div className="h-7 bg-gray-200 rounded w-12 mb-2" />
                <div className="h-3.5 bg-gray-100 rounded w-24" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stats grid */}
      {canViewGlobalTaskData && !isLoading && stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatsCard label="Total Tasks" value={stats.total} icon={CheckSquare} color="blue" />
          <StatsCard label="In Progress" value={stats.inProgress} icon={Clock} color="yellow" />
          <StatsCard label="Completed" value={stats.done} icon={CheckCircle2} color="green" />
          <StatsCard label="Overdue" value={stats.overdue} icon={AlertTriangle} color="red" />
          <StatsCard label="Due Today" value={stats.dueToday ?? 0} icon={CalendarClock} color="orange" />
          <StatsCard label="Backlog" value={stats.backlog} icon={ListTodo} color="gray" />
          <StatsCard label="Waiting" value={stats.waiting} icon={Hourglass} color="purple" />
          <StatsCard
            label="Completion Rate"
            value={stats.total > 0 ? Math.round((stats.done / stats.total) * 100) : 0}
            icon={BarChart3}
            color="green"
            suffix="%"
          />
        </div>
      )}

      {/* Charts row */}
      {canViewGlobalTaskData && !isLoading && stats && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          {/* Pie chart */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Tasks by Status</h3>
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: any) => [v, "Tasks"]} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-gray-400 text-sm">
                No task data yet
              </div>
            )}
            <div className="flex flex-wrap gap-3 mt-2">
              {pieData.map((d) => (
                <div key={d.name} className="flex items-center gap-1.5 text-xs text-gray-600">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ background: d.color }} />
                  {d.name} ({d.value})
                </div>
              ))}
            </div>
          </div>

          {/* Bar chart */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-4">Tasks by Employee</h3>
            {employeeData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={employeeData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="Done" fill="#10b981" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="In Progress" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="Overdue" fill="#ef4444" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[220px] flex items-center justify-center text-gray-400 text-sm">
                No employee data yet
              </div>
            )}
          </div>
        </div>
      )}

      {/* Three-col bottom */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* My Tasks */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">My Tasks</h3>
            <Link href="/my-tasks" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
              View all →
            </Link>
          </div>
          {myTasks.length === 0 ? (
            <div className="py-8 text-center text-gray-400 text-sm">No tasks assigned to you or created by you</div>
          ) : (
            <div className="space-y-2">
              {myTasks.map((task) => (
                <TaskRow key={task.id} task={task} />
              ))}
            </div>
          )}
        </div>

        {/* Due Today */}
        {canViewGlobalTaskData && (
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">
                Due Today
                {dueTodayTasks.length > 0 && (
                  <span className="ml-2 bg-amber-100 text-amber-600 text-xs px-2 py-0.5 rounded-full font-semibold">
                    {dueTodayTasks.length}
                  </span>
                )}
              </h3>
              <Link href="/tasks?dueToday=true" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
                View all →
              </Link>
            </div>
            {dueTodayTasks.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-sm flex flex-col items-center gap-2">
                <Sunrise className="w-8 h-8 text-amber-300" />
                <span>Nothing due today — enjoy the calm!</span>
              </div>
            ) : (
              <div className="space-y-2">
                {dueTodayTasks.map((task) => (
                  <TaskRow key={task.id} task={task} showAssignee />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Overdue Tasks */}
        {canViewGlobalTaskData && (
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">
                Overdue Tasks
                {overdueTasks.length > 0 && (
                  <span className="ml-2 bg-red-100 text-red-600 text-xs px-2 py-0.5 rounded-full font-semibold">
                    {overdueTasks.length}
                  </span>
                )}
              </h3>
              <Link href="/tasks?overdue=true" className="text-xs text-blue-600 hover:text-blue-700 font-medium">
                View all →
              </Link>
            </div>
            {overdueTasks.length === 0 ? (
              <div className="py-8 text-center text-gray-400 text-sm flex flex-col items-center gap-2">
                <PartyPopper className="w-8 h-8 text-green-400" />
                <span>No overdue tasks — you&apos;re all caught up!</span>
              </div>
            ) : (
              <div className="space-y-2">
                {overdueTasks.map((task) => (
                  <TaskRow key={task.id} task={task} showAssignee />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TaskRow({ task, showAssignee }: { task: Task; showAssignee?: boolean }) {
  const overdue = isOverdue(task.dueDate, task.status);
  const today = isDueToday(task.dueDate);
  const p = PRIORITY_CONFIG[task.priority];
  const s = STATUS_CONFIG[task.status];

  return (
    <Link
      href={`/tasks/${task.id}`}
      className={`flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors border-l-2 ${
        overdue ? "border-l-red-400" : today ? "border-l-amber-400" : "border-l-transparent"
      }`}
    >
      <div className={`w-2 h-2 rounded-full flex-shrink-0 ${s.dot}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{task.title}</p>
        <div className="flex items-center gap-2 mt-0.5">
          {showAssignee && task.assignee && (
            <span className="text-xs text-gray-400">{task.assignee.name}</span>
          )}
          {task.dueDate && (
            <span className={`text-xs ${overdue ? "text-red-500 font-medium" : "text-gray-400"}`}>
              {overdue ? "Overdue · " : "Due "}
              {formatDate(task.dueDate)}
            </span>
          )}
        </div>
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${p.bg} ${p.color}`}>
        {p.label}
      </span>
    </Link>
  );
}

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
