"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { Task, TaskStatus } from "@/types";
import {
  formatDate, isOverdue, isDueToday,
  PRIORITY_CONFIG, STATUS_CONFIG, getInitials,
} from "@/lib/utils";
import { AlertCircle, MessageSquare, Paperclip, GripVertical } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";

interface TaskKanbanProps {
  tasks: Task[];
  isLoading?: boolean;
}

const COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: "BACKLOG", label: "Backlog" },
  { status: "TODO", label: "To Do" },
  { status: "IN_PROGRESS", label: "In Progress" },
  { status: "WAITING", label: "Waiting" },
  { status: "DONE", label: "Done" },
];

export function TaskKanban({ tasks, isLoading }: TaskKanbanProps) {
  const queryClient = useQueryClient();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overColumn, setOverColumn] = useState<TaskStatus | null>(null);
  const dragTask = useRef<Task | null>(null);

  const updateStatus = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: TaskStatus }) => {
      const res = await fetch(`/api/tasks/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("Failed to update");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: () => toast.error("Failed to update status"),
  });

  function handleDragStart(e: React.DragEvent, task: Task) {
    dragTask.current = task;
    setDraggingId(task.id);
    e.dataTransfer.effectAllowed = "move";
  }

  function handleDragEnd() {
    setDraggingId(null);
    setOverColumn(null);
    dragTask.current = null;
  }

  function handleColumnDragOver(e: React.DragEvent, status: TaskStatus) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setOverColumn(status);
  }

  function handleColumnDrop(e: React.DragEvent, status: TaskStatus) {
    e.preventDefault();
    if (dragTask.current && dragTask.current.status !== status) {
      updateStatus.mutate({ id: dragTask.current.id, status });
      toast.success(`Moved to ${COLUMNS.find((c) => c.status === status)?.label}`);
    }
    setDraggingId(null);
    setOverColumn(null);
    dragTask.current = null;
  }

  if (isLoading) {
    return (
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map((col) => (
          <div key={col.status} className="flex-shrink-0 w-64">
            <div className="h-8 bg-gray-100 rounded animate-pulse mb-3" />
            {[1, 2].map((i) => (
              <div key={i} className="h-28 bg-gray-100 rounded-xl animate-pulse mb-2" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-4">
      {COLUMNS.map((col) => {
        const colTasks = tasks.filter((t) => t.status === col.status);
        const s = STATUS_CONFIG[col.status];
        const isDragOver = overColumn === col.status;

        return (
          <div
            key={col.status}
            className="flex-shrink-0 w-72"
            onDragOver={(e) => handleColumnDragOver(e, col.status)}
            onDragLeave={() => setOverColumn(null)}
            onDrop={(e) => handleColumnDrop(e, col.status)}
          >
            {/* Column header */}
            <div className="flex items-center justify-between mb-3 px-1">
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${s.dot}`} />
                <span className="font-bold text-gray-800 text-sm tracking-tight">{col.label}</span>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${s.bg} ${s.color}`}>
                {colTasks.length}
              </span>
            </div>

            {/* Drop zone */}
            <div
              className={`space-y-2 min-h-16 rounded-xl transition-all ${
                isDragOver ? "bg-blue-50/60 ring-2 ring-blue-300 ring-dashed p-1" : ""
              }`}
            >
              {colTasks.length === 0 ? (
                <div className={`h-16 border-2 border-dashed rounded-xl flex items-center justify-center text-xs transition-colors ${
                  isDragOver ? "border-blue-300 text-blue-400" : "border-gray-100 text-gray-300"
                }`}>
                  {isDragOver ? "Drop here" : "Empty"}
                </div>
              ) : (
                colTasks.map((task) => (
                  <KanbanCard
                    key={task.id}
                    task={task}
                    isDragging={draggingId === task.id}
                    onDragStart={(e) => handleDragStart(e, task)}
                    onDragEnd={handleDragEnd}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function KanbanCard({
  task,
  isDragging,
  onDragStart,
  onDragEnd,
}: {
  task: Task;
  isDragging: boolean;
  onDragStart: (e: React.DragEvent) => void;
  onDragEnd: () => void;
}) {
  const overdue = isOverdue(task.dueDate, task.status);
  const today = isDueToday(task.dueDate);
  const p = PRIORITY_CONFIG[task.priority];

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`bg-white rounded-xl border p-3 shadow-sm hover:shadow-md transition-all cursor-grab active:cursor-grabbing select-none ${
        isDragging
          ? "opacity-40 scale-95 ring-2 ring-blue-300"
          : overdue
          ? "border-red-200 border-l-4 border-l-red-400"
          : today
          ? "border-amber-200 border-l-4 border-l-amber-400"
          : "border-gray-100"
      }`}
    >
      <div className="flex items-start gap-1.5 mb-2">
        <GripVertical className="w-3.5 h-3.5 text-gray-300 flex-shrink-0 mt-0.5" />
        <Link href={`/tasks/${task.id}`} className="block flex-1" onClick={(e) => e.stopPropagation()}>
          <p className="text-sm font-medium text-gray-900 line-clamp-2 hover:text-blue-600 transition-colors">
            {task.title}
          </p>
        </Link>
      </div>

      {task.assignee && (
        <div className="flex items-center gap-1.5 mb-2">
          <div className="w-5 h-5 bg-blue-100 rounded-full flex items-center justify-center text-blue-700 text-[10px] font-bold">
            {getInitials(task.assignee.name)}
          </div>
          <span className="text-xs text-gray-500">{task.assignee.name.split(" ")[0]}</span>
        </div>
      )}

      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${p.bg} ${p.color}`}>
          {p.label}
        </span>

        {task.dueDate && (
          <span className={`text-xs flex items-center gap-1 ${overdue ? "text-red-500" : today ? "text-amber-500" : "text-gray-400"}`}>
            {overdue && <AlertCircle className="w-3 h-3" />}
            {formatDate(task.dueDate)}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 mt-2">
        {(task._count?.comments ?? 0) > 0 && (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <MessageSquare className="w-3 h-3" />
            {task._count!.comments}
          </span>
        )}
        {(task._count?.attachments ?? 0) > 0 && (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <Paperclip className="w-3 h-3" />
            {task._count!.attachments}
          </span>
        )}
      </div>

    </div>
  );
}
