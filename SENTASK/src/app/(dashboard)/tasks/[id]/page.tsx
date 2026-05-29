"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { useRouter, useParams } from "next/navigation";
import toast from "react-hot-toast";
import Link from "next/link";
import { ActivityLog, Priority, Task, TaskComment, TaskStatus, User } from "@/types";
import {
  formatDate, formatDateTime, formatRelative,
  isOverdue, isDueToday, PRIORITY_CONFIG, STATUS_CONFIG,
  REPEAT_LABELS, getInitials,
} from "@/lib/utils";
import { canAccessTask, canManageTasks } from "@/lib/access";
import {
  ArrowLeft, Edit2, Trash2, Send, Clock, User2,
  Building2, Flag, RefreshCw, Calendar, AlertCircle,
  CheckCircle2, Loader2, History, MessageSquare, Plus,
  Archive, UserCheck, RotateCcw, Pencil, X, Check,
  Paperclip, FileText, Image as ImageIcon, Tag, Timer, Link2, Mail,
  Search, UserPlus, Users,
} from "lucide-react";

function getActivityIcon(action: string) {
  if (action === "task.created") return <Plus className="w-3 h-3 text-green-600" />;
  if (action === "task.archived") return <Archive className="w-3 h-3 text-red-500" />;
  if (action === "comment.added") return <MessageSquare className="w-3 h-3 text-blue-500" />;
  if (action === "task.recurring_created") return <RotateCcw className="w-3 h-3 text-purple-500" />;
  if (action.includes("assigneeId")) return <UserCheck className="w-3 h-3 text-indigo-500" />;
  if (action.includes("status")) return <CheckCircle2 className="w-3 h-3 text-yellow-600" />;
  if (action.includes("dueDate") || action.includes("calendar")) return <Calendar className="w-3 h-3 text-sky-500" />;
  if (action.includes("priority")) return <Flag className="w-3 h-3 text-orange-500" />;
  return <History className="w-3 h-3 text-gray-400" />;
}

function describeActivity(log: ActivityLog): string {
  const { action, field, oldValue, newValue } = log;

  const statusLabel = (v: string | null | undefined) =>
    v ? (STATUS_CONFIG[v as TaskStatus]?.label ?? v) : "—";
  const priorityLabel = (v: string | null | undefined) =>
    v ? (PRIORITY_CONFIG[v as Priority]?.label ?? v) : "—";

  switch (action) {
    case "task.created": return "created this task";
    case "task.archived": return "archived this task";
    case "comment.added": return "added a comment";
    case "task.recurring_created": return "created a new recurring instance";
    case "user.login": return "logged in";
    case "user.password_reset_completed": return "reset their password";
  }

  if (field === "status")
    return `changed status from ${statusLabel(oldValue)} to ${statusLabel(newValue)}`;
  if (field === "priority")
    return `changed priority from ${priorityLabel(oldValue)} to ${priorityLabel(newValue)}`;
  if (field === "assigneeId")
    return `changed the assignee`;
  if (field === "dueDate")
    return `changed due date to ${newValue ? formatDate(newValue) : "none"}`;
  if (field === "title")
    return `updated the title`;
  if (field === "createCalendarEvent")
    return newValue === "true" ? "enabled calendar sync" : "disabled calendar sync";

  return action.replace("task.", "").replace(/_/g, " ");
}

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null);
  const [editingCommentText, setEditingCommentText] = useState("");
  const [uploadingFile, setUploadingFile] = useState(false);
  const [newSubTask, setNewSubTask] = useState("");
  const [logMinutes, setLogMinutes] = useState("");
  const [logNote, setLogNote] = useState("");
  const [depSearchId, setDepSearchId] = useState("");
  const [depQuery, setDepQuery] = useState("");
  const [depResults, setDepResults] = useState<any[]>([]);
  const [depSearchOpen, setDepSearchOpen] = useState(false);
  const depSearchRef = useRef<HTMLDivElement>(null);

  // Assignee edit state
  const [editingAssignees, setEditingAssignees] = useState(false);
  const [draftAssigneeId, setDraftAssigneeId] = useState("");
  const [draftCoIds, setDraftCoIds] = useState<string[]>([]);
  const [assigneeSearch, setAssigneeSearch] = useState("");
  const [savingAssignees, setSavingAssignees] = useState(false);

  const { data: task, isLoading } = useQuery<Task>({
    queryKey: ["task", params.id],
    queryFn: async () => {
      const res = await fetch(`/api/tasks/${params.id}`);
      if (!res.ok) throw new Error("Not found");
      return res.json();
    },
  });

  const { data: allUsers = [] } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: async () => (await fetch("/api/users")).json(),
  });

  const updateStatus = useMutation({
    mutationFn: async (status: TaskStatus) => {
      const res = await fetch(`/api/tasks/${params.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      toast.success("Status updated");
    },
  });

  const deleteTask = useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/tasks/${params.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed");
    },
    onSuccess: () => {
      toast.success("Task archived");
      router.push("/tasks");
    },
  });

  async function uploadFile(file: File) {
    if (!file) return;
    setUploadingFile(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch(`/api/tasks/${params.id}/attachments`, { method: "POST", body: fd });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Upload failed");
      }
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
      toast.success("File attached");
    } catch (e: any) {
      toast.error(e.message || "Upload failed");
    } finally {
      setUploadingFile(false);
    }
  }

  const { data: subTasks = [], refetch: refetchSubTasks } = useQuery<any[]>({
    queryKey: ["subtasks", params.id],
    queryFn: async () => {
      const res = await fetch(`/api/tasks/${params.id}/subtasks`);
      return res.json();
    },
    enabled: !!params.id,
  });

  async function addSubTask() {
    if (!newSubTask.trim()) return;
    await fetch(`/api/tasks/${params.id}/subtasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: newSubTask.trim() }),
    });
    setNewSubTask("");
    refetchSubTasks();
  }

  async function toggleSubTask(subtaskId: string, isDone: boolean) {
    await fetch(`/api/tasks/${params.id}/subtasks/${subtaskId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ isDone }),
    });
    refetchSubTasks();
  }

  const { data: timeData, refetch: refetchTime } = useQuery<{ entries: any[]; totalMinutes: number }>({
    queryKey: ["time", params.id],
    queryFn: async () => {
      const res = await fetch(`/api/tasks/${params.id}/time`);
      return res.json();
    },
    enabled: !!params.id,
  });

  async function logTime() {
    const mins = parseInt(logMinutes);
    if (!mins || mins < 1) return;
    await fetch(`/api/tasks/${params.id}/time`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ minutes: mins, note: logNote || null }),
    });
    setLogMinutes("");
    setLogNote("");
    refetchTime();
    toast.success("Time logged");
  }

  const { data: depsData, refetch: refetchDeps } = useQuery<{ blockedBy: any[]; blocking: any[] }>({
    queryKey: ["deps", params.id],
    queryFn: async () => {
      const res = await fetch(`/api/tasks/${params.id}/dependencies`);
      return res.json();
    },
    enabled: !!params.id,
  });

  useEffect(() => {
    if (depQuery.length < 2) { setDepResults([]); return; }
    const t = setTimeout(async () => {
      const res = await fetch(`/api/search?q=${encodeURIComponent(depQuery)}`);
      if (res.ok) {
        const data = await res.json();
        setDepResults((data.tasks || []).filter((t: any) => t.id !== params.id));
      }
    }, 200);
    return () => clearTimeout(t);
  }, [depQuery, params.id]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (depSearchRef.current && !depSearchRef.current.contains(e.target as Node)) {
        setDepSearchOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function addDependency() {
    if (!depSearchId.trim()) return;
    const res = await fetch(`/api/tasks/${params.id}/dependencies`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dependsOnId: depSearchId.trim() }),
    });
    if (res.ok) {
      setDepSearchId("");
      refetchDeps();
      toast.success("Dependency added");
    } else {
      const err = await res.json();
      toast.error(err.error || "Failed to add dependency");
    }
  }

  async function removeDependency(dependsOnId: string) {
    await fetch(`/api/tasks/${params.id}/dependencies/${dependsOnId}`, { method: "DELETE" });
    refetchDeps();
    toast.success("Dependency removed");
  }

  async function deleteTimeEntry(entryId: string) {
    await fetch(`/api/tasks/${params.id}/time/${entryId}`, { method: "DELETE" });
    refetchTime();
  }

  async function deleteSubTask(subtaskId: string) {
    await fetch(`/api/tasks/${params.id}/subtasks/${subtaskId}`, { method: "DELETE" });
    refetchSubTasks();
  }

  async function deleteAttachment(attachmentId: string) {
    try {
      const res = await fetch(`/api/tasks/${params.id}/attachments/${attachmentId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed");
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
      toast.success("Attachment removed");
    } catch {
      toast.error("Failed to remove attachment");
    }
  }

  async function saveEditComment(commentId: string) {
    if (!editingCommentText.trim()) return;
    try {
      const res = await fetch(`/api/tasks/${params.id}/comments/${commentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editingCommentText.trim() }),
      });
      if (!res.ok) throw new Error("Failed");
      setEditingCommentId(null);
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
    } catch {
      toast.error("Failed to update comment");
    }
  }

  async function deleteComment(commentId: string) {
    try {
      const res = await fetch(`/api/tasks/${params.id}/comments/${commentId}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed");
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
      toast.success("Comment deleted");
    } catch {
      toast.error("Failed to delete comment");
    }
  }

  function openAssigneeEditor() {
    setDraftAssigneeId(task?.assigneeId || "");
    setDraftCoIds((task as any)?.coAssigneeIds || []);
    setAssigneeSearch("");
    setEditingAssignees(true);
  }

  async function saveAssignees() {
    setSavingAssignees(true);
    try {
      const res = await fetch(`/api/tasks/${params.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assigneeId: draftAssigneeId || null, coAssigneeIds: draftCoIds }),
      });
      if (!res.ok) throw new Error("Failed");
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      setEditingAssignees(false);
      toast.success("Assignees updated");
    } catch {
      toast.error("Failed to update assignees");
    } finally {
      setSavingAssignees(false);
    }
  }

  async function submitComment() {
    if (!comment.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`/api/tasks/${params.id}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: comment.trim() }),
      });
      if (!res.ok) throw new Error("Failed");
      setComment("");
      queryClient.invalidateQueries({ queryKey: ["task", params.id] });
      toast.success("Comment added");
    } catch {
      toast.error("Failed to add comment");
    } finally {
      setSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!task) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">Task not found</p>
        <Link href="/tasks" className="text-blue-600 mt-2 inline-block">← Back to tasks</Link>
      </div>
    );
  }

  const overdue = isOverdue(task.dueDate, task.status);
  const today = isDueToday(task.dueDate);
  const p = PRIORITY_CONFIG[task.priority];
  const s = STATUS_CONFIG[task.status];
  const canEdit = canAccessTask(session?.user, task);
  const canArchive = canManageTasks(session?.user) && canAccessTask(session?.user, task);
  const comments = ((task as any).comments as TaskComment[] | undefined) || [];
  const activityLogs = ((task as any).activityLogs as ActivityLog[] | undefined) || [];

  return (
    <div className="animate-fade-in max-w-5xl">
      {/* Back */}
      <div className="mb-4">
        <Link
          href="/tasks"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Tasks
        </Link>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Main content */}
        <div className="xl:col-span-2 space-y-4">
          {/* Task header */}
          <div className={`bg-white rounded-xl border p-5 ${overdue ? "border-l-4 border-l-red-400" : today ? "border-l-4 border-l-amber-400" : "border-gray-100"}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-2">
                  {overdue && (
                    <span className="flex items-center gap-1 text-xs text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full font-medium">
                      <AlertCircle className="w-3 h-3" />
                      Overdue
                    </span>
                  )}
                  {today && !overdue && (
                    <span className="text-xs text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full font-medium">
                      Due Today
                    </span>
                  )}
                  {task.template && (
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                      {task.template.name}
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-bold text-gray-900">{task.title}</h2>
                {task.description ? (
                  <p className="text-gray-600 mt-3 text-sm leading-relaxed whitespace-pre-wrap">
                    {task.description}
                  </p>
                ) : canEdit ? (
                  <Link
                    href={`/tasks/${task.id}/edit`}
                    className="inline-block mt-3 text-sm text-gray-400 hover:text-blue-500 italic transition-colors"
                  >
                    No description — click Edit to add one
                  </Link>
                ) : (
                  <p className="mt-3 text-sm text-gray-400 italic">No description</p>
                )}
              </div>

              {canEdit && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <Link
                    href={`/tasks/${task.id}/edit`}
                    className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-600 transition-colors"
                  >
                    <Edit2 className="w-4 h-4" />
                  </Link>
                  {canArchive && (
                    <button
                      onClick={() => setShowArchiveConfirm(true)}
                      className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:border-red-300 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Status quick change */}
            <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap gap-2">
              {(["BACKLOG", "TODO", "IN_PROGRESS", "WAITING", "DONE"] as TaskStatus[]).map((st) => {
                const sc = STATUS_CONFIG[st];
                const isActive = task.status === st;
                const isPending = updateStatus.isPending;
                return (
                  <button
                    key={st}
                    onClick={() => { if (!isPending) updateStatus.mutate(st); }}
                    disabled={isPending}
                    className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-colors disabled:cursor-wait ${
                      isActive
                        ? `${sc.bg} ${sc.color} border-current`
                        : "border-gray-200 text-gray-400 hover:border-gray-300 hover:text-gray-600"
                    }`}
                  >
                    {isPending && isActive
                      ? <Loader2 className="w-2.5 h-2.5 animate-spin" />
                      : <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                    }
                    {sc.label}
                  </button>
                );
              })}
            </div>

            {task.notes && (
              <div className="mt-4 p-3 bg-amber-50 border border-amber-100 rounded-lg text-sm text-amber-800">
                <p className="font-medium text-xs text-amber-600 mb-1">Notes</p>
                {task.notes}
              </div>
            )}
          </div>

          {/* Checklist */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2 text-sm">
                <CheckCircle2 className="w-4 h-4 text-gray-400" />
                Checklist
                {subTasks.length > 0 && (
                  <span className="text-xs text-gray-500">
                    {subTasks.filter((s: any) => s.isDone).length}/{subTasks.length}
                  </span>
                )}
              </h3>
            </div>
            {subTasks.length > 0 && (
              <div className="w-full bg-gray-100 rounded-full h-1.5 mb-3">
                <div
                  className="bg-green-500 h-1.5 rounded-full transition-all"
                  style={{ width: `${(subTasks.filter((s: any) => s.isDone).length / subTasks.length) * 100}%` }}
                />
              </div>
            )}
            <div className="space-y-1.5 mb-3">
              {subTasks.map((s: any) => (
                <div key={s.id} className="flex items-center gap-2 group">
                  <button
                    onClick={() => toggleSubTask(s.id, !s.isDone)}
                    className={`w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors ${
                      s.isDone ? "bg-green-500 border-green-500 text-white" : "border-gray-300 hover:border-green-400"
                    }`}
                  >
                    {s.isDone && <Check className="w-2.5 h-2.5" />}
                  </button>
                  <span className={`text-sm flex-1 ${s.isDone ? "line-through text-gray-400" : "text-gray-700"}`}>
                    {s.title}
                  </span>
                  <button
                    onClick={() => deleteSubTask(s.id)}
                    className="p-0.5 rounded text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={newSubTask}
                onChange={(e) => setNewSubTask(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addSubTask()}
                placeholder="Add a checklist item…"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={addSubTask}
                disabled={!newSubTask.trim()}
                className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-lg transition-colors disabled:opacity-40"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Comments */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-4">
              Comments
              {comments.length > 0 && (
                <span className="ml-2 text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">
                  {comments.length}
                </span>
              )}
            </h3>

            <div className="space-y-4 mb-5">
              {comments.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-4">No comments yet</p>
              ) : (
                comments.map((c) => (
                  <div key={c.id} className="flex gap-3 group">
                    <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 text-xs font-bold flex-shrink-0 mt-0.5">
                      {getInitials(c.author.name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-gray-900">{c.author.name}</span>
                        <span className="text-xs text-gray-400">{formatRelative(c.createdAt)}</span>
                        {c.createdAt !== c.updatedAt && (
                          <span className="text-xs text-gray-300">(edited)</span>
                        )}
                        {(c.authorId === session?.user?.id || session?.user?.role === "ADMIN") && (
                          <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {c.authorId === session?.user?.id && editingCommentId !== c.id && (
                              <button
                                onClick={() => { setEditingCommentId(c.id); setEditingCommentText(c.content); }}
                                className="p-1 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50"
                              >
                                <Pencil className="w-3 h-3" />
                              </button>
                            )}
                            <button
                              onClick={() => deleteComment(c.id)}
                              className="p-1 rounded text-gray-400 hover:text-red-600 hover:bg-red-50"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        )}
                      </div>
                      {editingCommentId === c.id ? (
                        <div className="flex gap-2">
                          <textarea
                            value={editingCommentText}
                            onChange={(e) => setEditingCommentText(e.target.value)}
                            rows={2}
                            className="flex-1 border border-blue-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                          />
                          <div className="flex flex-col gap-1">
                            <button onClick={() => saveEditComment(c.id)} className="p-1.5 rounded bg-blue-600 text-white hover:bg-blue-700">
                              <Check className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => setEditingCommentId(null)} className="p-1.5 rounded bg-gray-100 text-gray-600 hover:bg-gray-200">
                              <X className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg px-3 py-2">
                          {c.content.split(/(@[\w.]+)/g).map((part, i) =>
                            /^@[\w.]+$/.test(part) ? (
                              <span key={i} className="text-blue-600 font-medium bg-blue-50 px-0.5 rounded">{part}</span>
                            ) : (
                              part
                            )
                          )}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Add comment */}
            <div className="flex gap-3">
              <div className="w-7 h-7 bg-[#1e3a8a] rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mt-0.5">
                {getInitials(session?.user?.name || "U")}
              </div>
              <div className="flex-1 flex gap-2">
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Add a comment..."
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitComment();
                  }}
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <button
                  onClick={submitComment}
                  disabled={submitting || !comment.trim()}
                  className="flex-shrink-0 bg-[#1e3a8a] hover:bg-[#1e40af] text-white p-2.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-1.5 ml-10">Cmd+Enter to submit</p>
          </div>
          {/* Activity log */}
          {activityLogs.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2 text-sm">
                <History className="w-4 h-4 text-gray-400" />
                Activity
              </h3>
              <div className="relative">
                <div className="absolute left-3 top-0 bottom-0 w-px bg-gray-100" />
                <div className="space-y-4">
                  {activityLogs.map((log) => (
                    <div key={log.id} className="flex gap-3 items-start pl-1">
                      <div className="w-6 h-6 rounded-full bg-gray-50 border border-gray-100 flex items-center justify-center flex-shrink-0 mt-0.5 z-10">
                        {getActivityIcon(log.action)}
                      </div>
                      <div className="flex-1 min-w-0 pb-1">
                        <p className="text-sm text-gray-700 leading-snug">
                          <span className="font-medium text-gray-900">
                            {log.user?.name ?? "System"}
                          </span>{" "}
                          {describeActivity(log)}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">{formatRelative(log.createdAt)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
          {/* Time Log */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2 text-sm">
              <Timer className="w-4 h-4 text-gray-400" />
              Time Log
              {(timeData?.totalMinutes ?? 0) > 0 && (
                <span className="text-xs bg-indigo-50 text-indigo-600 border border-indigo-200 px-2 py-0.5 rounded-full font-medium ml-1">
                  {timeData!.totalMinutes >= 60
                    ? `${Math.floor(timeData!.totalMinutes / 60)}h ${timeData!.totalMinutes % 60}m total`
                    : `${timeData!.totalMinutes}m total`}
                </span>
              )}
            </h3>
            <div className="space-y-2 mb-4">
              {(timeData?.entries.length ?? 0) === 0 ? (
                <p className="text-xs text-gray-400 text-center py-2">No time logged yet</p>
              ) : (
                timeData!.entries.map((e: any) => (
                  <div key={e.id} className="flex items-center gap-2 group text-sm">
                    <div className="w-6 h-6 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-700 text-xs font-bold flex-shrink-0">
                      {getInitials(e.user.name)}
                    </div>
                    <span className="text-indigo-600 font-semibold flex-shrink-0">
                      {e.minutes >= 60 ? `${Math.floor(e.minutes / 60)}h ${e.minutes % 60}m` : `${e.minutes}m`}
                    </span>
                    {e.note && <span className="text-gray-500 text-xs truncate flex-1">{e.note}</span>}
                    <span className="text-xs text-gray-400 flex-shrink-0">{formatDate(e.date)}</span>
                    {(e.user.id === session?.user?.id || session?.user?.role === "ADMIN") && (
                      <button
                        onClick={() => deleteTimeEntry(e.id)}
                        className="p-0.5 rounded text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
            <div className="flex gap-2">
              <input
                type="number"
                value={logMinutes}
                onChange={(e) => setLogMinutes(e.target.value)}
                placeholder="Minutes"
                min={1}
                max={1440}
                className="w-24 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                type="text"
                value={logNote}
                onChange={(e) => setLogNote(e.target.value)}
                placeholder="Optional note"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={logTime}
                disabled={!logMinutes || parseInt(logMinutes) < 1}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm rounded-lg transition-colors disabled:opacity-40"
              >
                Log
              </button>
            </div>
          </div>
        </div>

        {/* Sidebar info */}
        <div className="space-y-4">
          {/* Details */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-4 text-sm">Details</h3>
            <dl className="space-y-3">
              <DetailRow
                icon={<Flag className="w-3.5 h-3.5" />}
                label="Priority"
                value={
                  <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${p.bg} ${p.color}`}>
                    {p.label}
                  </span>
                }
              />
              <DetailRow
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                label="Status"
                value={
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${s.bg} ${s.color}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                    {s.label}
                  </span>
                }
              />
              {/* Assignees row with edit */}
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <DetailRow
                    icon={<User2 className="w-3.5 h-3.5" />}
                    label={task.coAssignees && task.coAssignees.length > 0 ? "Assignees" : "Assignee"}
                    value={
                      task.assignee ? (
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-1.5">
                            <div className="w-5 h-5 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
                              {getInitials(task.assignee.name)}
                            </div>
                            <span className="text-xs text-gray-700">{task.assignee.name}</span>
                            <span className="text-[10px] text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded-full">primary</span>
                          </div>
                          {(task.coAssignees || []).map((u: any) => (
                            <div key={u.id} className="flex items-center gap-1.5">
                              <div className="w-5 h-5 bg-gradient-to-br from-purple-500 to-purple-700 rounded-full flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
                                {getInitials(u.name)}
                              </div>
                              <span className="text-xs text-gray-700">{u.name}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-gray-400">Unassigned</span>
                      )
                    }
                  />
                </div>
                {canEdit && !editingAssignees && (
                  <button
                    onClick={openAssigneeEditor}
                    className="flex-shrink-0 p-1 rounded text-gray-300 hover:text-blue-500 hover:bg-blue-50 transition-colors mt-0.5"
                    title="Edit assignees"
                  >
                    <Pencil className="w-3 h-3" />
                  </button>
                )}
              </div>

              {/* Inline assignee editor */}
              {editingAssignees && (
                <div className="col-span-2 mt-1 p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-blue-700 flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      Edit Assignees
                    </span>
                    <button onClick={() => setEditingAssignees(false)} className="text-gray-400 hover:text-gray-600">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-gray-400" />
                    <input
                      type="text"
                      value={assigneeSearch}
                      onChange={(e) => setAssigneeSearch(e.target.value)}
                      placeholder="Search people…"
                      className="w-full pl-7 pr-3 py-1.5 border border-gray-200 rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white"
                    />
                  </div>
                  <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
                    {allUsers
                      .filter((u) => !assigneeSearch || u.name.toLowerCase().includes(assigneeSearch.toLowerCase()))
                      .map((u) => {
                        const isPrimary = u.id === draftAssigneeId;
                        const isCo = draftCoIds.includes(u.id);
                        const isSelected = isPrimary || isCo;
                        function toggleUser() {
                          if (isPrimary) {
                            const [next, ...rest] = draftCoIds;
                            setDraftAssigneeId(next || "");
                            setDraftCoIds(rest);
                          } else if (isCo) {
                            setDraftCoIds((prev) => prev.filter((id) => id !== u.id));
                          } else {
                            if (!draftAssigneeId) setDraftAssigneeId(u.id);
                            else setDraftCoIds((prev) => [...prev, u.id]);
                          }
                        }
                        return (
                          <button
                            key={u.id}
                            type="button"
                            onClick={toggleUser}
                            className={`flex items-center gap-1.5 px-2 py-1 rounded-full border text-xs font-medium transition-all ${
                              isSelected
                                ? "bg-blue-600 border-blue-600 text-white"
                                : "bg-white border-gray-200 text-gray-600 hover:border-blue-300"
                            }`}
                          >
                            <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0 ${isSelected ? "bg-white/20 text-white" : "bg-blue-100 text-blue-700"}`}>
                              {u.name.charAt(0).toUpperCase()}
                            </div>
                            {u.name.split(" ")[0]}
                            {isPrimary && <span className="text-[9px] opacity-75">primary</span>}
                            {isSelected && <Check className="w-2.5 h-2.5" />}
                          </button>
                        );
                      })}
                  </div>
                  {(draftAssigneeId || draftCoIds.length > 0) && (
                    <div className="flex flex-wrap gap-1 items-center">
                      <span className="text-[10px] text-gray-500">Selected:</span>
                      {draftAssigneeId && (
                        <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                          {allUsers.find((u) => u.id === draftAssigneeId)?.name?.split(" ")[0]} (primary)
                        </span>
                      )}
                      {draftCoIds.map((id) => {
                        const u = allUsers.find((u) => u.id === id);
                        return u ? (
                          <span key={id} className="text-[10px] bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full">
                            {u.name.split(" ")[0]}
                          </span>
                        ) : null;
                      })}
                      <button
                        type="button"
                        onClick={() => { setDraftAssigneeId(""); setDraftCoIds([]); }}
                        className="text-[10px] text-red-400 hover:text-red-600 ml-1"
                      >
                        Clear
                      </button>
                    </div>
                  )}
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={saveAssignees}
                      disabled={savingAssignees}
                      className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-md transition-colors disabled:opacity-50"
                    >
                      {savingAssignees ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                      Save
                    </button>
                    <button
                      onClick={() => setEditingAssignees(false)}
                      className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-md transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              <DetailRow
                icon={<Building2 className="w-3.5 h-3.5" />}
                label="Department"
                value={
                  task.department ? (
                    <span className="text-xs text-gray-600">{task.department.name}</span>
                  ) : (
                    <span className="text-xs text-gray-400">None</span>
                  )
                }
              />
              <DetailRow
                icon={<Calendar className="w-3.5 h-3.5" />}
                label="Due Date"
                value={
                  task.dueDate ? (
                    <span className={`text-xs font-medium ${overdue ? "text-red-600" : "text-gray-700"}`}>
                      {formatDate(task.dueDate)}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-400">No due date</span>
                  )
                }
              />
              <DetailRow
                icon={<RefreshCw className="w-3.5 h-3.5" />}
                label="Repeat"
                value={<span className="text-xs text-gray-700">{REPEAT_LABELS[task.repeatType]}</span>}
              />
              <DetailRow
                icon={<Calendar className="w-3.5 h-3.5" />}
                label="Google Calendar"
                value={
                  task.createCalendarEvent ? (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-gray-700">
                        {task.calendarSyncStatus || "NONE"}
                      </span>
                      {task.googleCalendarHtmlLink && (
                        <a
                          href={task.googleCalendarHtmlLink}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-blue-600 hover:text-blue-700"
                        >
                          Open Calendar Event
                        </a>
                      )}
                      {task.calendarSyncError && (
                        <span className="text-xs text-red-500">{task.calendarSyncError}</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-gray-400">Not synced</span>
                  )
                }
              />
              <DetailRow
                icon={<User2 className="w-3.5 h-3.5" />}
                label="Created by"
                value={<span className="text-xs text-gray-700">{task.creator.name}</span>}
              />
              {(task as any).tags?.length > 0 && (
                <DetailRow
                  icon={<Tag className="w-3.5 h-3.5" />}
                  label="Tags"
                  value={
                    <div className="flex flex-wrap gap-1 justify-end">
                      {((task as any).tags as string[]).map((t) => (
                        <span key={t} className="text-xs bg-blue-50 text-blue-600 border border-blue-200 px-2 py-0.5 rounded-full font-medium">
                          #{t}
                        </span>
                      ))}
                    </div>
                  }
                />
              )}
              {(task as any).estimatedMinutes != null && (
                <DetailRow
                  icon={<Timer className="w-3.5 h-3.5" />}
                  label="Estimated"
                  value={
                    <span className="text-xs text-gray-700">
                      {(task as any).estimatedMinutes >= 60
                        ? `${Math.floor((task as any).estimatedMinutes / 60)}h ${(task as any).estimatedMinutes % 60}m`
                        : `${(task as any).estimatedMinutes}m`}
                    </span>
                  }
                />
              )}
              <DetailRow
                icon={<Clock className="w-3.5 h-3.5" />}
                label="Created"
                value={<span className="text-xs text-gray-500">{formatDateTime(task.createdAt)}</span>}
              />
              {task.completedAt && (
                <DetailRow
                  icon={<CheckCircle2 className="w-3.5 h-3.5 text-green-500" />}
                  label="Completed"
                  value={<span className="text-xs text-green-600 font-medium">{formatDate(task.completedAt)}</span>}
                />
              )}
            </dl>
          </div>

          {/* Attachments */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2">
                <Paperclip className="w-4 h-4 text-gray-400" />
                Attachments
                {(task as any).attachments?.length > 0 && (
                  <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded-full">
                    {(task as any).attachments.length}
                  </span>
                )}
              </h3>
              <label className="cursor-pointer">
                <input
                  type="file"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
                  disabled={uploadingFile}
                />
                <span className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 border border-blue-200 hover:border-blue-400 px-2 py-1 rounded-lg transition-colors">
                  {uploadingFile ? <Loader2 className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                  {uploadingFile ? "Uploading…" : "Add"}
                </span>
              </label>
            </div>
            {(task as any).attachments?.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-2">No attachments yet</p>
            ) : (
              <div className="space-y-2">
                {((task as any).attachments as any[])?.map((att: any) => (
                  <div key={att.id} className="flex items-center gap-2 group">
                    {att.mimeType.startsWith("image/") ? (
                      <ImageIcon className="w-4 h-4 text-blue-400 flex-shrink-0" />
                    ) : (
                      <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    )}
                    <a
                      href={att.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 text-xs text-blue-600 hover:text-blue-700 truncate"
                      title={att.originalName}
                    >
                      {att.originalName}
                    </a>
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {(att.size / 1024 < 1024
                        ? `${(att.size / 1024).toFixed(0)} KB`
                        : `${(att.size / 1024 / 1024).toFixed(1)} MB`)}
                    </span>
                    {(att.uploaderId === session?.user?.id || session?.user?.role === "ADMIN") && (
                      <button
                        onClick={() => deleteAttachment(att.id)}
                        className="p-0.5 rounded text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Dependencies */}
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 text-sm flex items-center gap-2 mb-3">
              <Link2 className="w-4 h-4 text-gray-400" />
              Dependencies
            </h3>
            {(depsData?.blockedBy.length ?? 0) > 0 && (
              <div className="mb-3">
                <p className="text-xs font-medium text-gray-500 mb-1.5">Blocked by</p>
                <div className="space-y-1.5">
                  {depsData!.blockedBy.map((dep: any) => (
                    <div key={dep.id} className="flex items-center gap-2 group">
                      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dep.status === "DONE" ? "bg-green-400" : "bg-amber-400"}`} />
                      <Link href={`/tasks/${dep.id}`} className="text-xs text-blue-600 hover:text-blue-700 truncate flex-1">
                        {dep.title}
                      </Link>
                      {dep.status === "DONE" && <Check className="w-3 h-3 text-green-500 flex-shrink-0" />}
                      <button
                        onClick={() => removeDependency(dep.id)}
                        className="p-0.5 rounded text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {(depsData?.blocking.length ?? 0) > 0 && (
              <div className="mb-3">
                <p className="text-xs font-medium text-gray-500 mb-1.5">Blocks</p>
                <div className="space-y-1.5">
                  {depsData!.blocking.map((dep: any) => (
                    <div key={dep.id} className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-red-400 flex-shrink-0" />
                      <Link href={`/tasks/${dep.id}`} className="text-xs text-blue-600 hover:text-blue-700 truncate">
                        {dep.title}
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="relative" ref={depSearchRef}>
              <input
                type="text"
                value={depQuery}
                onChange={(e) => { setDepQuery(e.target.value); setDepSearchOpen(true); setDepSearchId(""); }}
                onFocus={() => depQuery.length >= 2 && setDepSearchOpen(true)}
                placeholder="Search tasks to block on…"
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              {depSearchId && (
                <div className="mt-1 text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-2 py-1 flex items-center justify-between">
                  <span>Selected: task ready to add</span>
                  <button
                    onClick={async () => {
                      await addDependency();
                      setDepQuery("");
                      setDepSearchId("");
                    }}
                    className="ml-2 px-2 py-0.5 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
                  >
                    Add
                  </button>
                </div>
              )}
              {depSearchOpen && depResults.length > 0 && !depSearchId && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-40 overflow-y-auto">
                  {depResults.map((r: any) => (
                    <button
                      key={r.id}
                      onClick={() => { setDepSearchId(r.id); setDepQuery(r.title); setDepSearchOpen(false); }}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 transition-colors border-b border-gray-50 last:border-0"
                    >
                      <p className="font-medium text-gray-900 truncate">{r.title}</p>
                      <p className="text-gray-400 mt-0.5">{r.status?.replace(/_/g, " ")} · {r.priority}</p>
                    </button>
                  ))}
                </div>
              )}
              {depSearchOpen && depQuery.length >= 2 && depResults.length === 0 && !depSearchId && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 px-3 py-2 text-xs text-gray-400">
                  No tasks found
                </div>
              )}
            </div>
          </div>

          {/* Email recipients */}
          {task.emailRecipients.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3 text-sm">Email Recipients</h3>
              <div className="space-y-1">
                {task.emailRecipients.map((e) => (
                  <div key={e} className="flex items-center gap-1.5 text-xs text-gray-600">
                    <Mail className="w-3 h-3 text-gray-400 flex-shrink-0" />
                    {e}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      {/* Archive confirmation dialog */}
      {showArchiveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => setShowArchiveConfirm(false)}
          />
          <div className="relative bg-white rounded-xl shadow-xl border border-gray-100 p-6 max-w-sm w-full animate-fade-in">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center flex-shrink-0">
                <Trash2 className="w-5 h-5 text-red-500" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">Archive this task?</h3>
                <p className="text-sm text-gray-500 mt-0.5">This will hide the task from all views.</p>
              </div>
            </div>
            <div className="flex gap-3 mt-5">
              <button
                onClick={() => setShowArchiveConfirm(false)}
                className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => { setShowArchiveConfirm(false); deleteTask.mutate(); }}
                disabled={deleteTask.isPending}
                className="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
              >
                {deleteTask.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Archive
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-1.5 text-gray-400 flex-shrink-0 mt-0.5">
        {icon}
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <div className="text-right">{value}</div>
    </div>
  );
}
