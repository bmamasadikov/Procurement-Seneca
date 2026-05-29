import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { TaskForm } from "@/components/tasks/TaskForm";
import { canManageTasks } from "@/lib/access";

export default async function NewTaskPage() {
  const session = await auth();
  if (!session) redirect("/login");
  if (!canManageTasks(session.user)) redirect("/my-tasks");

  return (
    <div className="animate-fade-in">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900">Create New Task</h2>
        <p className="text-gray-500 text-sm mt-1">
          Fill in the details below to create and assign a new task.
        </p>
      </div>
      <TaskForm mode="create" />
    </div>
  );
}
