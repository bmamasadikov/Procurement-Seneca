"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { User } from "@/types";
import { X, Plus, Loader2, Zap } from "lucide-react";
import toast from "react-hot-toast";

export function QuickTaskModal() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState("MEDIUM");
  const [dueDate, setDueDate] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: users = [] } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: async () => (await fetch("/api/users")).json(),
    enabled: open,
  });

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "N") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => titleRef.current?.focus(), 50);
  }, [open]);

  function reset() {
    setTitle("");
    setPriority("MEDIUM");
    setDueDate("");
    setAssigneeId("");
  }

  async function handleSubmit(e: React.FormEvent, openAfter = false) {
    e.preventDefault();
    if (!title.trim()) { toast.error("Title required"); return; }
    setSubmitting(true);
    try {
      const res = await fetch("/api/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          priority,
          status: "TODO",
          dueDate: dueDate || null,
          assigneeId: assigneeId || null,
        }),
      });
      if (!res.ok) throw new Error("Failed");
      const task = await res.json();
      toast.success("Task created!");
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
      reset();
      if (openAfter) {
        setOpen(false);
        router.push(`/tasks/${task.id}`);
      } else {
        titleRef.current?.focus();
      }
    } catch {
      toast.error("Failed to create task");
    } finally {
      setSubmitting(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <div className="relative bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-lg animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-100 rounded-lg flex items-center justify-center">
              <Zap className="w-4 h-4 text-blue-600" />
            </div>
            <span className="font-semibold text-gray-900">Quick Task</span>
          </div>
          <div className="flex items-center gap-2">
            <kbd className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">⌘⇧N</kbd>
            <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={(e) => handleSubmit(e, false)} className="p-5 space-y-4">
          <input
            ref={titleRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="What needs to be done?"
            className="w-full text-base font-medium border-0 border-b-2 border-gray-200 focus:border-blue-500 focus:outline-none pb-2 placeholder-gray-300 transition-colors"
          />

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Due Date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Assign to</label>
              <select
                value={assigneeId}
                onChange={(e) => setAssigneeId(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                <option value="">Unassigned</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>{u.name.split(" ")[0]}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Due date shortcuts */}
          <div className="flex gap-1.5">
            {[
              { label: "Today", days: 0 },
              { label: "Tomorrow", days: 1 },
              { label: "+1 week", days: 7 },
            ].map(({ label, days }) => {
              const d = new Date();
              d.setDate(d.getDate() + days);
              const val = d.toISOString().split("T")[0];
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => setDueDate(val)}
                  className={`text-xs px-2 py-0.5 rounded-md border transition-colors ${
                    dueDate === val
                      ? "bg-blue-600 border-blue-600 text-white"
                      : "border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-600"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              type="submit"
              disabled={submitting || !title.trim()}
              className="flex items-center gap-1.5 bg-[#1e3a8a] hover:bg-[#1e40af] text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
            >
              {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              Create
            </button>
            <button
              type="button"
              disabled={submitting || !title.trim()}
              onClick={(e) => handleSubmit(e as any, true)}
              className="flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              Create & Open
            </button>
            <span className="ml-auto text-xs text-gray-400">Enter = create another</span>
          </div>
        </form>
      </div>
    </div>
  );
}
