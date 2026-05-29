"use client";

import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { TrendingUp, Users, CheckCircle2, AlertTriangle } from "lucide-react";
import { getInitials } from "@/lib/utils";
import { hasFullTaskAccess } from "@/lib/access";
import { StatsCard } from "@/components/dashboard/StatsCard";

export default function ReportsPage() {
  const { data: session } = useSession();
  if (session?.user && !hasFullTaskAccess(session.user)) redirect("/dashboard");

  const { data, isLoading } = useQuery({
    queryKey: ["reports-detail"],
    queryFn: async () => {
      const res = await fetch("/api/reports");
      return res.json();
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        {[1, 2, 3].map((i) => <div key={i} className="h-48 bg-gray-100 rounded-xl" />)}
      </div>
    );
  }

  const { stats, employeeStats = [], deptStats = [] } = data || {};

  const completionData = deptStats.map((d: any) => ({
    name: d.name,
    "Completion %": d.completionRate,
    Total: d.total,
    Overdue: d.overdue,
  }));

  const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Summary cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatsCard label="Total Tasks" value={stats.total} icon={TrendingUp} color="blue" />
          <StatsCard
            label="Completed"
            value={stats.done}
            icon={CheckCircle2}
            color="green"
            subtitle={`${stats.total > 0 ? Math.round((stats.done / stats.total) * 100) : 0}% completion rate`}
          />
          <StatsCard label="Overdue" value={stats.overdue} icon={AlertTriangle} color="red" />
          <StatsCard label="Team Members" value={employeeStats.length} icon={Users} color="purple" />
        </div>
      )}

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {/* Department completion rates */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Department Performance</h3>
          {completionData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={completionData} margin={{ left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="Completion %" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Overdue" fill="#ef4444" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400 text-sm">
              No department data yet
            </div>
          )}
        </div>

        {/* Employee performance */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Task Distribution by Employee</h3>
          {employeeStats.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={employeeStats.slice(0, 8).map((e: any) => ({ name: e.name.split(" ")[0], value: e.total }))}
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  dataKey="value"
                  label={({ name, percent }: { name: string; percent?: number }) =>
                    `${name} ${((percent || 0) * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {employeeStats.slice(0, 8).map((_: any, i: number) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400 text-sm">
              No employee data yet
            </div>
          )}
        </div>
      </div>

      {/* Employee table */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">Employee Performance Summary</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-50 bg-gray-50/50">
                <th className="text-left text-xs font-semibold text-gray-500 px-5 py-3">Employee</th>
                <th className="text-left text-xs font-semibold text-gray-500 px-3 py-3">Department</th>
                <th className="text-center text-xs font-semibold text-gray-500 px-3 py-3">Total</th>
                <th className="text-center text-xs font-semibold text-gray-500 px-3 py-3">Done</th>
                <th className="text-center text-xs font-semibold text-gray-500 px-3 py-3">In Progress</th>
                <th className="text-center text-xs font-semibold text-gray-500 px-3 py-3">Overdue</th>
                <th className="text-center text-xs font-semibold text-gray-500 px-3 py-3">Rate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {employeeStats.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-gray-400 text-sm">
                    No data available
                  </td>
                </tr>
              ) : (
                employeeStats.map((e: any) => (
                  <tr key={e.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 text-xs font-bold">
                          {getInitials(e.name)}
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900">{e.name}</p>
                          {e.jobTitle && <p className="text-xs text-gray-400">{e.jobTitle}</p>}
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      {e.department ? (
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md">
                          {e.department}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center text-sm font-medium text-gray-900">{e.total}</td>
                    <td className="px-3 py-3 text-center">
                      <span className="text-sm font-medium text-green-600">{e.done}</span>
                    </td>
                    <td className="px-3 py-3 text-center">
                      <span className="text-sm font-medium text-yellow-600">{e.inProgress}</span>
                    </td>
                    <td className="px-3 py-3 text-center">
                      {e.overdue > 0 ? (
                        <span className="text-sm font-bold text-red-600">{e.overdue}</span>
                      ) : (
                        <span className="text-sm text-gray-400">0</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <div className="flex-1 max-w-16 bg-gray-100 rounded-full h-1.5">
                          <div
                            className="bg-green-500 h-1.5 rounded-full"
                            style={{ width: `${e.completionRate}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium text-gray-600 w-8">{e.completionRate}%</span>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
