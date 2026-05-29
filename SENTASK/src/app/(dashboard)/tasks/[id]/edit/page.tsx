"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Task } from "@/types";
import { TaskForm } from "@/components/tasks/TaskForm";
import { canAccessTask } from "@/lib/access";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

export default function EditTaskPage() {
  const params = useParams();
  const { data: session } = useSession();

  const { data: task, isLoading } = useQuery<Task>({
    queryKey: ["task", params.id],
    queryFn: async () => {
      const res = await fetch(`/api/tasks/${params.id}`);
      if (!res.ok) throw new Error("Not found");
      return res.json();
    },
  });

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
        <Link href="/tasks" className="text-blue-600 mt-2 inline-block">← Back</Link>
      </div>
    );
  }

  const canEdit = canAccessTask(session?.user, task);

  if (!canEdit) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">You don't have permission to edit this task.</p>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <Link
          href={`/tasks/${params.id}`}
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 font-medium mb-3"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Task
        </Link>
        <h2 className="text-xl font-bold text-gray-900">Edit Task</h2>
        <p className="text-gray-500 text-sm mt-1 truncate">{task.title}</p>
      </div>
      <TaskForm mode="edit" initialData={task} />
    </div>
  );
}
