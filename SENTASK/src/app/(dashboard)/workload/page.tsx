"use client";

import { useQuery } from "@tanstack/react-query";
import { getInitials } from "@/lib/utils";
import { Users, TrendingUp } from "lucide-react";

interface WorkloadUser {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string | null;
  jobTitle?: string | null;
  department?: { name: string; color: string } | null;
  total: number;
  open: number;
  done: number;
  overdue: number;
  inProgress: number;
  todo: number;
  critical: number;
}

const LOAD_THRESHOLDS = { low: 3, medium: 6, high: 10 };

function getLoadColor(open: number) {
  if (open === 0) return { bar: "bg-gray-200", label: "text-gray-400", badge: "bg-gray-100 text-gray-500" };
  if (open <= LOAD_THRESHOLDS.low) return { bar: "bg-green-400", label: "text-green-600", badge: "bg-green-50 text-green-700" };
  if (open <= LOAD_THRESHOLDS.medium) return { bar: "bg-amber-400", label: "text-amber-600", badge: "bg-amber-50 text-amber-700" };
  if (open <= LOAD_THRESHOLDS.high) return { bar: "bg-orange-500", label: "text-orange-600", badge: "bg-orange-50 text-orange-700" };
  return { bar: "bg-red-500", label: "text-red-600", badge: "bg-red-50 text-red-700" };
}

function loadLabel(open: number) {
  if (open === 0) return "Free";
  if (open <= LOAD_THRESHOLDS.low) return "Light";
  if (open <= LOAD_THRESHOLDS.medium) return "Moderate";
  if (open <= LOAD_THRESHOLDS.high) return "Heavy";
  return "Overloaded";
}

export default function WorkloadPage() {
  const { data: workload, isLoading } = useQuery<WorkloadUser[]>({
    queryKey: ["workload"],
    queryFn: async () => {
      const res = await fetch("/api/workload");
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
  });

  if (isLoading) {
    return (
      <div className="animate-fade-in space-y-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-100 p-4 animate-pulse">
              <div className="h-3.5 bg-gray-100 rounded w-24 mb-3" />
              <div className="h-8 bg-gray-200 rounded w-16" />
            </div>
          ))}
        </div>
        <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <div className="h-4 bg-gray-100 rounded w-32 animate-pulse" />
          </div>
          <div className="divide-y divide-gray-50">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="px-5 py-3.5 flex items-center gap-4 animate-pulse">
                <div className="w-8 h-8 rounded-full bg-gray-100 flex-shrink-0" />
                <div className="flex-1">
                  <div className="h-3.5 bg-gray-200 rounded w-32 mb-2" />
                  <div className="h-2 bg-gray-100 rounded-full w-full" />
                </div>
                <div className="w-20 text-right space-y-1">
                  <div className="h-3.5 bg-gray-200 rounded" />
                  <div className="h-3 bg-gray-100 rounded w-16 ml-auto" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!workload) return null;

  const maxOpen = Math.max(...workload.map((u) => u.open), 1);
  const totalOpen = workload.reduce((s, u) => s + u.open, 0);
  const overloaded = workload.filter((u) => u.open > LOAD_THRESHOLDS.high).length;
  const avgOpen = workload.length > 0 ? (totalOpen / workload.length).toFixed(1) : "0";

  const sorted = [...workload].sort((a, b) => b.open - a.open);

  return (
    <div className="animate-fade-in space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-xs text-gray-500 font-medium">Team members</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{workload.length}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-xs text-gray-500 font-medium">Total open tasks</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{totalOpen}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-xs text-gray-500 font-medium">Avg tasks / person</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{avgOpen}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-4">
          <p className="text-xs text-gray-500 font-medium">Overloaded (&gt;{LOAD_THRESHOLDS.high})</p>
          <p className={`text-2xl font-bold mt-1 ${overloaded > 0 ? "text-red-600" : "text-green-600"}`}>{overloaded}</p>
        </div>
      </div>

      {/* User workload bars */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
          <Users className="w-4 h-4 text-gray-400" />
          <h2 className="font-semibold text-gray-900 text-sm">Team Workload</h2>
          <p className="text-xs text-gray-400 ml-1">Open tasks per person</p>
        </div>
        <div className="divide-y divide-gray-50">
          {sorted.map((u) => {
            const { bar, badge } = getLoadColor(u.open);
            const barWidth = maxOpen > 0 ? `${(u.open / maxOpen) * 100}%` : "0%";
            return (
              <div key={u.id} className="px-5 py-3.5 flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                  {getInitials(u.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-900 truncate">{u.name}</span>
                    {u.department && (
                      <span
                        className="text-xs px-1.5 py-0.5 rounded-full font-medium hidden sm:inline-flex"
                        style={{ backgroundColor: u.department.color + "20", color: u.department.color }}
                      >
                        {u.department.name}
                      </span>
                    )}
                    <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${badge}`}>
                      {loadLabel(u.open)}
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${bar}`}
                      style={{ width: barWidth }}
                    />
                  </div>
                </div>
                <div className="text-right flex-shrink-0 min-w-[5rem]">
                  <p className="text-sm font-bold text-gray-900">{u.open} open</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {u.done} done
                    {u.overdue > 0 && <span className="text-red-500 ml-1">· {u.overdue} overdue</span>}
                    {u.critical > 0 && <span className="text-orange-500 ml-1">· {u.critical} critical</span>}
                  </p>
                </div>
              </div>
            );
          })}
          {workload.length === 0 && (
            <div className="px-5 py-10 text-center">
              <p className="text-gray-400 text-sm">No team members found</p>
            </div>
          )}
        </div>
      </div>

      {/* Status breakdown table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-gray-400" />
          <h2 className="font-semibold text-gray-900 text-sm">Task Breakdown</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs text-gray-500 uppercase tracking-wide">
                <th className="px-5 py-2.5 text-left font-semibold">Person</th>
                <th className="px-3 py-2.5 text-center font-semibold">In Progress</th>
                <th className="px-3 py-2.5 text-center font-semibold">Todo / Waiting</th>
                <th className="px-3 py-2.5 text-center font-semibold">Overdue</th>
                <th className="px-3 py-2.5 text-center font-semibold">Critical</th>
                <th className="px-3 py-2.5 text-center font-semibold">Done</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sorted.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50/50">
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 text-xs font-bold flex-shrink-0">
                        {getInitials(u.name)}
                      </div>
                      <span className="font-medium text-gray-900 truncate max-w-32">{u.name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`font-semibold ${u.inProgress > 0 ? "text-blue-600" : "text-gray-300"}`}>{u.inProgress}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`font-semibold ${u.todo > 0 ? "text-gray-700" : "text-gray-300"}`}>{u.todo}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`font-semibold ${u.overdue > 0 ? "text-red-600" : "text-gray-300"}`}>{u.overdue}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`font-semibold ${u.critical > 0 ? "text-orange-600" : "text-gray-300"}`}>{u.critical}</span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`font-semibold ${u.done > 0 ? "text-green-600" : "text-gray-300"}`}>{u.done}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
