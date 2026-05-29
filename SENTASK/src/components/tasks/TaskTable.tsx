"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Task } from "@/types";
import {
  formatDate, isOverdue, isDueToday,
  PRIORITY_CONFIG, STATUS_CONFIG, REPEAT_LABELS, getInitials,
} from "@/lib/utils";
import {
  RefreshCw, MessageSquare, Paperclip, AlertCircle, ClipboardList,
  CheckSquare, Square, Trash2, CheckCircle2, Flag, Loader2,
  ArrowUp, ArrowDown, ArrowUpDown, Check,
} from "lucide-react";
import toast from "react-hot-toast";

type SortField = "title" | "status" | "priority" | "dueDate" | "assignee";
type SortDir = "asc" | "desc";

const PRIORITY_ORDER: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };
const STATUS_ORDER: Record<string, number> = { IN_PROGRESS: 0, TODO: 1, BACKLOG: 2, WAITING: 3, DONE: 4 };

interface TaskTableProps {
  tasks: Task[];
  isLoading?: boolean;
  onBulkSuccess?: () => void;
}

export function TaskTable({ tasks, isLoading, onBulkSuccess }: TaskTableProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkPending, setBulkPending] = useState(false);
  const [sortField, setSortField] = useState<SortField | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [completingIds, setCompletingIds] = useState<Set<string>>(new Set());

  async function quickComplete(taskId: string, e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    setCompletingIds((prev) => new Set([...prev, taskId]));
    try {
      await fetch(`/api/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "DONE" }),
      });
      toast.success("Task completed");
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      onBulkSuccess?.();
    } catch {
      toast.error("Failed");
    } finally {
      setCompletingIds((prev) => {
        const next = new Set(prev);
        next.delete(taskId);
        return next;
      });
    }
  }

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  }

  const sortedTasks = useMemo(() => {
    if (!sortField) return tasks;
    return [...tasks].sort((a, b) => {
      let cmp = 0;
      if (sortField === "title") cmp = a.title.localeCompare(b.title);
      else if (sortField === "status") cmp = (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9);
      else if (sortField === "priority") cmp = (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9);
      else if (sortField === "dueDate") {
        const da = a.dueDate ? new Date(a.dueDate).getTime() : Infinity;
        const db = b.dueDate ? new Date(b.dueDate).getTime() : Infinity;
        cmp = da - db;
      } else if (sortField === "assignee") {
        cmp = (a.assignee?.name ?? "").localeCompare(b.assignee?.name ?? "");
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [tasks, sortField, sortDir]);

  const allSelected = sortedTasks.length > 0 && sortedTasks.every((t) => selectedIds.has(t.id));

  function toggleAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(sortedTasks.map((t) => t.id)));
    }
  }

  function toggleOne(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function bulkAction(action: string, value?: string | null) {
    if (selectedIds.size === 0) return;
    setBulkPending(true);
    try {
      const res = await fetch("/api/tasks/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ids: [...selectedIds], value }),
      });
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      toast.success(`Updated ${data.updated} task${data.updated !== 1 ? "s" : ""}`);
      setSelectedIds(new Set());
      onBulkSuccess?.();
    } catch {
      toast.error("Bulk action failed");
    } finally {
      setBulkPending(false);
    }
  }

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="animate-pulse p-6 space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-12 bg-gray-100 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-100 p-12 text-center">
        <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mx-auto mb-3">
          <ClipboardList className="w-6 h-6 text-blue-400" />
        </div>
        <p className="text-gray-700 font-medium">No tasks found</p>
        <p className="text-gray-400 text-sm mt-1">Try adjusting your filters or create a new task</p>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Floating bulk action bar */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-gray-900 text-white px-4 py-2.5 rounded-2xl shadow-2xl border border-gray-700 animate-fade-in">
          <span className="text-sm font-semibold mr-1">{selectedIds.size} selected</span>
          <span className="w-px h-4 bg-gray-600 mx-1" />
          <button
            onClick={() => bulkAction("status", "DONE")}
            disabled={bulkPending}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded-lg transition-colors disabled:opacity-50"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Mark Done
          </button>
          <button
            onClick={() => bulkAction("status", "IN_PROGRESS")}
            disabled={bulkPending}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors disabled:opacity-50"
          >
            In Progress
          </button>
          <button
            onClick={() => bulkAction("priority", "HIGH")}
            disabled={bulkPending}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-orange-600 hover:bg-orange-500 rounded-lg transition-colors disabled:opacity-50"
          >
            <Flag className="w-3.5 h-3.5" />
            High Priority
          </button>
          <button
            onClick={() => { if (confirm(`Archive ${selectedIds.size} task(s)?`)) bulkAction("archive"); }}
            disabled={bulkPending}
            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 bg-red-600 hover:bg-red-500 rounded-lg transition-colors disabled:opacity-50"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Archive
          </button>
          {bulkPending && <Loader2 className="w-4 h-4 animate-spin ml-1" />}
          <button
            onClick={() => setSelectedIds(new Set())}
            className="ml-1 text-xs text-gray-400 hover:text-white transition-colors"
          >
            ✕
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="px-4 py-3 w-8">
                  <button onClick={toggleAll} className="text-gray-400 hover:text-blue-600 transition-colors">
                    {allSelected ? (
                      <CheckSquare className="w-4 h-4 text-blue-600" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                </th>
                <SortTh label="Task" field="title" current={sortField} dir={sortDir} onSort={toggleSort} className="px-4 py-3" />
                <SortTh label="Assignee" field="assignee" current={sortField} dir={sortDir} onSort={toggleSort} className="px-3 py-3 hidden md:table-cell" />
                <th className="text-left text-xs font-semibold text-gray-500 px-3 py-3 uppercase tracking-wide hidden lg:table-cell">
                  Department
                </th>
                <SortTh label="Status" field="status" current={sortField} dir={sortDir} onSort={toggleSort} className="px-3 py-3" />
                <SortTh label="Priority" field="priority" current={sortField} dir={sortDir} onSort={toggleSort} className="px-3 py-3" />
                <SortTh label="Due Date" field="dueDate" current={sortField} dir={sortDir} onSort={toggleSort} className="px-3 py-3 hidden lg:table-cell" />
                <th className="text-left text-xs font-semibold text-gray-500 px-3 py-3 uppercase tracking-wide hidden xl:table-cell">
                  Repeat
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {sortedTasks.map((task) => {
                const overdue = isOverdue(task.dueDate, task.status);
                const today = isDueToday(task.dueDate);
                const p = PRIORITY_CONFIG[task.priority];
                const s = STATUS_CONFIG[task.status];
                const isSelected = selectedIds.has(task.id);

                return (
                  <tr
                    key={task.id}
                    onClick={() => router.push(`/tasks/${task.id}`)}
                    className={`hover:bg-blue-50/40 transition-colors cursor-pointer group ${
                      isSelected ? "bg-blue-50/60" : overdue ? "bg-red-50/30" : today ? "bg-amber-50/30" : ""
                    }`}
                  >
                    <td className="px-4 py-3 w-8" onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => toggleOne(task.id)} className="text-gray-400 hover:text-blue-600 transition-colors">
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-blue-600" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3 max-w-xs">
                      <div className="flex items-start gap-2">
                        {/* Quick-complete circle */}
                        <button
                          onClick={(e) => quickComplete(task.id, e)}
                          disabled={task.status === "DONE" || completingIds.has(task.id)}
                          title={task.status === "DONE" ? "Completed" : "Mark as done"}
                          className={`w-4 h-4 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center transition-all ${
                            task.status === "DONE"
                              ? "border-green-500 bg-green-500 cursor-default"
                              : completingIds.has(task.id)
                              ? "border-blue-300 bg-blue-50"
                              : "border-gray-300 hover:border-green-400 hover:bg-green-50"
                          }`}
                        >
                          {task.status === "DONE" && <Check className="w-2.5 h-2.5 text-white" />}
                          {completingIds.has(task.id) && <Loader2 className="w-2.5 h-2.5 text-blue-400 animate-spin" />}
                        </button>
                        <Link href={`/tasks/${task.id}`} onClick={(e) => e.stopPropagation()} className="group-hover:text-blue-600 transition-colors flex-1 min-w-0">
                        <div className="flex items-start gap-1.5">
                          {overdue && <AlertCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0 mt-0.5" />}
                          <div className="min-w-0">
                            <p className={`text-sm font-medium truncate max-w-[180px] group-hover:text-blue-600 ${task.status === "DONE" ? "line-through text-gray-400" : "text-gray-900"}`}>
                              {task.title}
                            </p>
                            {task.template && (
                              <p className="text-xs text-gray-400 mt-0.5">{task.template.name}</p>
                            )}
                            <div className="flex items-center gap-2 mt-1">
                              {(task._count?.comments ?? 0) > 0 && (
                                <span className="flex items-center gap-0.5 text-xs text-gray-400">
                                  <MessageSquare className="w-3 h-3" />
                                  {task._count!.comments}
                                </span>
                              )}
                              {(task._count?.attachments ?? 0) > 0 && (
                                <span className="flex items-center gap-0.5 text-xs text-gray-400">
                                  <Paperclip className="w-3 h-3" />
                                  {task._count!.attachments}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </Link>
                      </div>
                    </td>

                    <td className="px-3 py-3 hidden md:table-cell">
                      {task.assignee ? (
                        <div className="flex items-center gap-2">
                          {/* Stacked avatars: primary + co-assignees */}
                          <div className="flex -space-x-1.5">
                            <div
                              className="w-6 h-6 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white text-[9px] font-bold flex-shrink-0 ring-2 ring-white"
                              title={task.assignee.name}
                            >
                              {getInitials(task.assignee.name)}
                            </div>
                            {(task.coAssignees || []).slice(0, 3).map((u: any) => (
                              <div
                                key={u.id}
                                className="w-6 h-6 bg-gradient-to-br from-purple-500 to-purple-700 rounded-full flex items-center justify-center text-white text-[9px] font-bold flex-shrink-0 ring-2 ring-white"
                                title={u.name}
                              >
                                {getInitials(u.name)}
                              </div>
                            ))}
                            {(task.coAssignees || []).length > 3 && (
                              <div className="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center text-gray-600 text-[9px] font-bold ring-2 ring-white">
                                +{(task.coAssignees || []).length - 3}
                              </div>
                            )}
                          </div>
                          <span className="text-sm text-gray-700 truncate max-w-20">
                            {task.assignee.name.split(" ")[0]}
                            {(task.coAssignees || []).length > 0 && (
                              <span className="text-gray-400 text-xs"> +{(task.coAssignees || []).length}</span>
                            )}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">Unassigned</span>
                      )}
                    </td>

                    <td className="px-3 py-3 hidden lg:table-cell">
                      {task.department ? (
                        <span className="text-xs text-gray-600 bg-gray-100 px-2 py-1 rounded-md">
                          {task.department.name}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-400">—</span>
                      )}
                    </td>

                    <td className="px-3 py-3">
                      <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${s.bg} ${s.color}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                        {s.label}
                      </span>
                    </td>

                    <td className="px-3 py-3">
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${p.bg} ${p.color}`}>
                        {p.label}
                      </span>
                    </td>

                    <td className="px-3 py-3 hidden lg:table-cell">
                      {task.dueDate ? (
                        <span className={`flex items-center gap-1 text-xs font-medium ${overdue ? "text-red-600" : today ? "text-amber-600" : "text-gray-600"}`}>
                          {overdue && <AlertCircle className="w-3 h-3 flex-shrink-0" />}
                          {formatDate(task.dueDate)}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>

                    <td className="px-3 py-3 hidden xl:table-cell">
                      {task.repeatType !== "NONE" ? (
                        <span className="inline-flex items-center gap-1 text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                          <RefreshCw className="w-3 h-3" />
                          {REPEAT_LABELS[task.repeatType]}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SortTh({
  label, field, current, dir, onSort, className,
}: {
  label: string;
  field: SortField;
  current: SortField | null;
  dir: SortDir;
  onSort: (f: SortField) => void;
  className?: string;
}) {
  const active = current === field;
  return (
    <th className={`text-left ${className}`}>
      <button
        onClick={() => onSort(field)}
        className="flex items-center gap-1 text-xs font-semibold text-gray-500 uppercase tracking-wide hover:text-gray-800 transition-colors group"
      >
        {label}
        {active ? (
          dir === "asc" ? <ArrowUp className="w-3 h-3 text-blue-500" /> : <ArrowDown className="w-3 h-3 text-blue-500" />
        ) : (
          <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-50 transition-opacity" />
        )}
      </button>
    </th>
  );
}
