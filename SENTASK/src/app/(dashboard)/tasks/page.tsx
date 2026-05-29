"use client";

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { Task, TaskFilters, PaginatedResponse } from "@/types";
import { TaskTable } from "@/components/tasks/TaskTable";
import { TaskFiltersBar } from "@/components/tasks/TaskFilters";
import { buildQueryString } from "@/lib/utils";
import { canManageTasks } from "@/lib/access";
import Link from "next/link";
import { Plus, LayoutGrid, List, ChevronLeft, ChevronRight, Download } from "lucide-react";
import { TaskKanban } from "@/components/tasks/TaskKanban";

export default function TasksPage() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const canCreateTasks = canManageTasks(session?.user);

  const [filters, setFilters] = useState<TaskFilters>({});
  const [view, setView] = useState<"table" | "kanban">("table");
  const [page, setPage] = useState(1);

  const queryString = buildQueryString({
    ...filters,
    page,
    pageSize: 25,
  });

  const { data, isLoading } = useQuery<PaginatedResponse<Task>>({
    queryKey: ["tasks", queryString],
    queryFn: async () => {
      const res = await fetch(`/api/tasks?${queryString}`);
      return res.json();
    },
  });

  const handleFiltersChange = useCallback((newFilters: TaskFilters) => {
    setFilters(newFilters);
    setPage(1);
  }, []);

  const tasks = data?.data || [];
  const total = data?.total || 0;
  const totalPages = data?.totalPages || 1;

  function exportCSV() {
    const header = ["Title", "Status", "Priority", "Assignee", "Department", "Due Date", "Repeat", "Tags", "Created"];
    const rows = tasks.map((t) => [
      `"${t.title.replace(/"/g, '""')}"`,
      t.status,
      t.priority,
      t.assignee?.name || "",
      (t.department as any)?.name || "",
      t.dueDate ? new Date(t.dueDate).toLocaleDateString() : "",
      t.repeatType,
      ((t as any).tags || []).join(";"),
      new Date(t.createdAt).toLocaleDateString(),
    ]);
    const csv = [header, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sentask-tasks-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          {isLoading ? (
            <div className="h-5 w-32 bg-gray-100 rounded animate-pulse" />
          ) : (
            <p className="text-gray-500 text-sm mt-0.5">
              {total} task{total !== 1 ? "s" : ""} total
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5 gap-0.5">
            <button
              onClick={() => setView("table")}
              className={`p-1.5 rounded-md transition-colors ${view === "table" ? "bg-white shadow text-gray-700" : "text-gray-400 hover:text-gray-600"}`}
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setView("kanban")}
              className={`p-1.5 rounded-md transition-colors ${view === "kanban" ? "bg-white shadow text-gray-700" : "text-gray-400 hover:text-gray-600"}`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>

          {tasks.length > 0 && (
            <button
              onClick={exportCSV}
              title="Export current page to CSV"
              className="flex items-center gap-1.5 border border-gray-200 text-gray-600 hover:border-gray-300 hover:text-gray-800 text-sm font-medium px-3 py-2 rounded-lg transition-colors"
            >
              <Download className="w-4 h-4" />
              CSV
            </button>
          )}

          {canCreateTasks && (
            <Link
              href="/tasks/new"
              className="flex items-center gap-1.5 bg-[#1e3a8a] hover:bg-[#1e40af] text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
            >
              <Plus className="w-4 h-4" />
              New Task
            </Link>
          )}
        </div>
      </div>

      {/* Filters */}
      <TaskFiltersBar filters={filters} onChange={handleFiltersChange} />

      {/* Content */}
      {view === "table" ? (
        <>
          <TaskTable
            tasks={tasks}
            isLoading={isLoading}
            onBulkSuccess={() => queryClient.invalidateQueries({ queryKey: ["tasks"] })}
          />

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Showing {(page - 1) * 25 + 1}–{Math.min(page * 25, total)} of {total}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 1}
                  className="p-2 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-sm text-gray-600 px-2">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page === totalPages}
                  className="p-2 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <TaskKanban tasks={tasks} isLoading={isLoading} />
      )}
    </div>
  );
}
