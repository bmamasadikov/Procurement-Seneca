"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { Task, TaskTemplate, User, Department, GoogleWorkspaceSettings } from "@/types";
import { EMAIL_RECIPIENTS } from "@/lib/utils";
import { Loader2, Plus, X, Tag, Timer, Search, UserPlus, Check } from "lucide-react";

interface TaskFormProps {
  initialData?: Partial<Task>;
  mode: "create" | "edit";
}

const PRIORITIES = [
  { value: "CRITICAL", label: "Critical", color: "text-red-600" },
  { value: "HIGH", label: "High", color: "text-orange-600" },
  { value: "MEDIUM", label: "Medium", color: "text-blue-600" },
  { value: "LOW", label: "Low", color: "text-gray-500" },
];

const STATUSES = [
  { value: "BACKLOG", label: "Backlog" },
  { value: "TODO", label: "To Do" },
  { value: "IN_PROGRESS", label: "In Progress" },
  { value: "WAITING", label: "Waiting" },
  { value: "DONE", label: "Done" },
];

const REPEATS = [
  { value: "NONE", label: "One-time" },
  { value: "DAILY", label: "Daily" },
  { value: "WEEKLY", label: "Weekly" },
  { value: "MONTHLY", label: "Monthly" },
];

export function TaskForm({ initialData, mode }: TaskFormProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [titleError, setTitleError] = useState("");

  // Form fields
  const [templateId, setTemplateId] = useState(initialData?.templateId || "");
  const [customTitle, setCustomTitle] = useState(initialData?.title || "");
  const [isCustom, setIsCustom] = useState(false);
  const [description, setDescription] = useState(initialData?.description || "");
  const [priority, setPriority] = useState(initialData?.priority || "MEDIUM");
  const [status, setStatus] = useState(initialData?.status || "TODO");
  const [repeatType, setRepeatType] = useState(initialData?.repeatType || "NONE");
  const [dueDate, setDueDate] = useState(
    initialData?.dueDate ? new Date(initialData.dueDate).toISOString().split("T")[0] : ""
  );
  const [startDate, setStartDate] = useState(
    initialData?.startDate ? new Date(initialData.startDate).toISOString().split("T")[0] : ""
  );
  const [assigneeId, setAssigneeId] = useState(initialData?.assigneeId || "");
  const [coAssigneeIds, setCoAssigneeIds] = useState<string[]>((initialData as any)?.coAssigneeIds || []);
  const [assigneeSearch, setAssigneeSearch] = useState("");
  const [departmentId, setDepartmentId] = useState(initialData?.departmentId || "");
  const [notes, setNotes] = useState(initialData?.notes || "");
  const [emailRecipients, setEmailRecipients] = useState<string[]>(initialData?.emailRecipients || []);
  const [createCalendarEvent, setCreateCalendarEvent] = useState(
    initialData?.createCalendarEvent || false
  );
  const [googleCalendarId, setGoogleCalendarId] = useState(initialData?.googleCalendarId || "");
  const [tags, setTags] = useState<string[]>((initialData as any)?.tags || []);
  const [tagInput, setTagInput] = useState("");
  const [estimatedMinutes, setEstimatedMinutes] = useState(
    (initialData as any)?.estimatedMinutes ? String((initialData as any).estimatedMinutes) : ""
  );
  const tagInputRef = useRef<HTMLInputElement>(null);

  // Data
  const { data: templates = [] } = useQuery<TaskTemplate[]>({
    queryKey: ["templates"],
    queryFn: async () => (await fetch("/api/templates")).json(),
  });

  const { data: users = [] } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: async () => (await fetch("/api/users")).json(),
  });

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: async () => (await fetch("/api/departments")).json(),
  });

  const { data: workspaceSettings } = useQuery<GoogleWorkspaceSettings>({
    queryKey: ["google-workspace-settings", "task-form"],
    queryFn: async () => {
      const res = await fetch("/api/settings/google-workspace");
      if (!res.ok) throw new Error("Failed to load Workspace settings");
      return res.json();
    },
  });

  useEffect(() => {
    if (!workspaceSettings || initialData) return;

    setCreateCalendarEvent(workspaceSettings.defaultCreateCalendarEvents);
    if (!googleCalendarId) {
      setGoogleCalendarId(
        workspaceSettings.defaultCalendarId === "primary"
          ? ""
          : workspaceSettings.defaultCalendarId
      );
    }
  }, [workspaceSettings, initialData, googleCalendarId]);

  // Derived title
  const selectedTemplate = templates.find((t) => t.id === templateId);
  const title = isCustom ? customTitle : selectedTemplate?.name || customTitle;

  function handleTemplateChange(value: string) {
    setTemplateId(value);
    const tmpl = templates.find((t) => t.id === value);
    if (tmpl?.name === "Custom") {
      setIsCustom(true);
      setCustomTitle("");
    } else {
      setIsCustom(false);
      if (tmpl) setCustomTitle(tmpl.name);
    }
  }

  function addTag() {
    const raw = tagInput.trim().toLowerCase().replace(/[^a-z0-9-_]/g, "");
    if (!raw || tags.includes(raw)) { setTagInput(""); return; }
    setTags((prev) => [...prev, raw]);
    setTagInput("");
  }

  function removeTag(t: string) {
    setTags((prev) => prev.filter((x) => x !== t));
  }

  function toggleEmailRecipient(email: string) {
    setEmailRecipients((prev) =>
      prev.includes(email) ? prev.filter((e) => e !== email) : [...prev, email]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) {
      setTitleError("Task title is required");
      return;
    }
    setTitleError("");

    setLoading(true);
    try {
      const body = {
        title: title.trim(),
        description: description || undefined,
        status,
        priority,
        repeatType,
        dueDate: dueDate || null,
        startDate: startDate || null,
        notes: notes || undefined,
        assigneeId: assigneeId || null,
        coAssigneeIds,
        departmentId: departmentId || null,
        templateId: templateId && !isCustom ? templateId : null,
        emailRecipients,
        createCalendarEvent,
        googleCalendarId: googleCalendarId || null,
        tags,
        estimatedMinutes: estimatedMinutes ? parseInt(estimatedMinutes) : null,
      };

      const url = mode === "create" ? "/api/tasks" : `/api/tasks/${initialData?.id}`;
      const method = mode === "create" ? "POST" : "PATCH";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to save task");
      }

      const task = await res.json();
      toast.success(mode === "create" ? "Task created!" : "Task updated!");
      router.push(`/tasks/${task.id}`);
    } catch (err: any) {
      toast.error(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-3xl">
      {/* Template & Title */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">Task Details</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Task Template
            </label>
            <select
              value={templateId}
              onChange={(e) => handleTemplateChange(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">— Select template —</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              Task Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={isCustom ? customTitle : (selectedTemplate?.name || customTitle)}
              onChange={(e) => { setCustomTitle(e.target.value); if (titleError) setTitleError(""); }}
              disabled={!isCustom && !!selectedTemplate && selectedTemplate.name !== "Custom"}
              placeholder={isCustom ? "Enter custom task title..." : "Select a template or enter title"}
              className={`w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 disabled:bg-gray-50 disabled:text-gray-500 ${
                titleError
                  ? "border-red-300 focus:ring-red-400"
                  : "border-gray-200 focus:ring-blue-500"
              }`}
            />
            {titleError ? (
              <p className="text-xs text-red-500 mt-1">{titleError}</p>
            ) : isCustom ? (
              <p className="text-xs text-blue-600 mt-1">Custom task — enter a title above</p>
            ) : null}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="Describe what needs to be done..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>
      </div>

      {/* Assignment */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">Assignment</h3>

        {/* Multi-assignee picker */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1.5">
            <UserPlus className="w-3.5 h-3.5 text-gray-400" />
            Assign to
            <span className="text-xs text-gray-400 font-normal ml-1">— select one or more people</span>
          </label>

          {/* Search box */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
            <input
              type="text"
              value={assigneeSearch}
              onChange={(e) => setAssigneeSearch(e.target.value)}
              placeholder="Search by name..."
              className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* User pills grid */}
          <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto pr-1">
            {users
              .filter((u) => !assigneeSearch || u.name.toLowerCase().includes(assigneeSearch.toLowerCase()))
              .map((u) => {
                const isPrimary = u.id === assigneeId;
                const isCo = coAssigneeIds.includes(u.id);
                const isSelected = isPrimary || isCo;

                function toggleUser() {
                  if (isPrimary) {
                    // deselect primary — promote first co-assignee if exists
                    const [next, ...rest] = coAssigneeIds;
                    setAssigneeId(next || "");
                    setCoAssigneeIds(rest || []);
                  } else if (isCo) {
                    setCoAssigneeIds((prev) => prev.filter((id) => id !== u.id));
                  } else {
                    // add: if no primary yet, make this primary; otherwise add as co
                    if (!assigneeId) {
                      setAssigneeId(u.id);
                    } else {
                      setCoAssigneeIds((prev) => [...prev, u.id]);
                    }
                  }
                }

                return (
                  <button
                    key={u.id}
                    type="button"
                    onClick={toggleUser}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm font-medium transition-all ${
                      isSelected
                        ? "bg-blue-600 border-blue-600 text-white shadow-sm"
                        : "bg-white border-gray-200 text-gray-700 hover:border-blue-300 hover:bg-blue-50"
                    }`}
                  >
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 ${
                      isSelected ? "bg-white/20 text-white" : "bg-blue-100 text-blue-700"
                    }`}>
                      {u.name.charAt(0).toUpperCase()}
                    </div>
                    <span className="truncate max-w-[100px]">{u.name.split(" ")[0]}</span>
                    {isPrimary && <span className="text-[10px] opacity-75 font-normal">primary</span>}
                    {isSelected && <Check className="w-3 h-3 flex-shrink-0" />}
                  </button>
                );
              })}
            {users.filter((u) => !assigneeSearch || u.name.toLowerCase().includes(assigneeSearch.toLowerCase())).length === 0 && (
              <p className="text-sm text-gray-400 py-2">No users match your search</p>
            )}
          </div>

          {/* Selected summary */}
          {(assigneeId || coAssigneeIds.length > 0) && (
            <div className="mt-3 flex flex-wrap gap-1.5 items-center">
              <span className="text-xs text-gray-500">Assigned to:</span>
              {assigneeId && (
                <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                  {users.find((u) => u.id === assigneeId)?.name?.split(" ")[0]} (primary)
                </span>
              )}
              {coAssigneeIds.map((id) => {
                const u = users.find((u) => u.id === id);
                return u ? (
                  <span key={id} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">
                    {u.name.split(" ")[0]}
                  </span>
                ) : null;
              })}
              {(assigneeId || coAssigneeIds.length > 0) && (
                <button
                  type="button"
                  onClick={() => { setAssigneeId(""); setCoAssigneeIds([]); }}
                  className="text-xs text-red-500 hover:text-red-700 ml-1 font-medium"
                >
                  Clear all
                </button>
              )}
            </div>
          )}
        </div>

        {/* Department */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Department</label>
          <div className="flex gap-2 items-start">
            <select
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="">— No department —</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
            {departmentId && (() => {
              const deptMembers = users.filter((u) => u.departmentId === departmentId);
              if (!deptMembers.length) return null;
              const deptName = departments.find((d) => d.id === departmentId)?.name || "department";
              return (
                <button
                  type="button"
                  onClick={() => {
                    const [first, ...rest] = deptMembers;
                    setAssigneeId(first.id);
                    setCoAssigneeIds(rest.map((u) => u.id));
                  }}
                  className="flex-shrink-0 text-xs px-3 py-2.5 rounded-lg border border-purple-200 text-purple-700 bg-purple-50 hover:bg-purple-100 transition-colors font-medium whitespace-nowrap"
                  title={`Assign all ${deptMembers.length} members of ${deptName}`}
                >
                  Assign all ({deptMembers.length})
                </button>
              );
            })()}
          </div>
          {departmentId && users.filter((u) => u.departmentId === departmentId).length > 0 && (
            <p className="text-xs text-gray-400 mt-1">
              {users.filter((u) => u.departmentId === departmentId).length} members in {departments.find((d) => d.id === departmentId)?.name}
            </p>
          )}
        </div>
      </div>

      {/* Settings */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">Settings</h3>

        {/* Row 1: Priority, Status, Repeat */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as any)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {PRIORITIES.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as any)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Repeat</label>
            <select
              value={repeatType}
              onChange={(e) => setRepeatType(e.target.value as any)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              {REPEATS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Row 2: Due Date + Start Date */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Due Date</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex flex-wrap gap-1.5 mt-2">
              {[
                { label: "Today", days: 0 },
                { label: "Tomorrow", days: 1 },
                { label: "+1 week", days: 7 },
                { label: "+1 month", days: 30 },
              ].map(({ label, days }) => {
                const d = new Date();
                d.setDate(d.getDate() + days);
                const val = d.toISOString().split("T")[0];
                return (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setDueDate(val)}
                    className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${
                      dueDate === val
                        ? "bg-blue-600 border-blue-600 text-white"
                        : "border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-600"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
              {dueDate && (
                <button
                  type="button"
                  onClick={() => setDueDate("")}
                  className="text-xs px-2.5 py-1 rounded-md border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Tags & Estimation */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">Tags & Estimation</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Tags */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5 text-gray-400" />
              Tags
            </label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {tags.map((t) => (
                <span key={t} className="flex items-center gap-1 bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium px-2 py-0.5 rounded-full">
                  #{t}
                  <button type="button" onClick={() => removeTag(t)} className="hover:text-red-500 transition-colors">
                    <X className="w-2.5 h-2.5" />
                  </button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                ref={tagInputRef}
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addTag(); } }}
                placeholder="Add tag and press Enter…"
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={addTag}
                disabled={!tagInput.trim()}
                className="px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm rounded-lg transition-colors disabled:opacity-40"
              >
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">Lowercase letters, numbers, hyphens only</p>
          </div>

          {/* Estimated time */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
              <Timer className="w-3.5 h-3.5 text-gray-400" />
              Estimated Duration (minutes)
            </label>
            <input
              type="number"
              value={estimatedMinutes}
              onChange={(e) => setEstimatedMinutes(e.target.value)}
              min={1}
              max={10080}
              placeholder="e.g. 60 = 1 hour"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {estimatedMinutes && parseInt(estimatedMinutes) >= 60 && (
              <p className="text-xs text-indigo-500 mt-1">
                = {Math.floor(parseInt(estimatedMinutes) / 60)}h {parseInt(estimatedMinutes) % 60}m
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Notes & Email */}
      <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-4">
        <h3 className="font-semibold text-gray-900 text-sm uppercase tracking-wide">
          Notifications & Notes
        </h3>

        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
          <div className="flex items-start gap-3">
            <input
              id="createCalendarEvent"
              type="checkbox"
              checked={createCalendarEvent}
              onChange={(e) => setCreateCalendarEvent(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <div className="flex-1">
              <label htmlFor="createCalendarEvent" className="block text-sm font-medium text-gray-800">
                Sync this task to Google Calendar
              </label>
              <p className="mt-1 text-xs text-gray-500">
                When enabled, SENTASK will create or update a Google Calendar event for this task.
              </p>
            </div>
          </div>

          {createCalendarEvent && (
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Target Calendar ID
              </label>
              <input
                type="text"
                value={googleCalendarId}
                onChange={(e) => setGoogleCalendarId(e.target.value)}
                placeholder="primary"
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-400">
                Leave empty to use the assignee&apos;s primary Google Workspace calendar, or keep the shared default loaded from Workspace Settings.
              </p>
            </div>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Also send email notification to:
          </label>
          <div className="flex flex-wrap gap-2">
            {EMAIL_RECIPIENTS.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => toggleEmailRecipient(r.value)}
                className={`text-sm px-3 py-1.5 rounded-lg border font-medium transition-colors ${
                  emailRecipients.includes(r.value)
                    ? "bg-blue-50 border-blue-300 text-blue-700"
                    : "bg-gray-50 border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                {emailRecipients.includes(r.value) ? "✓ " : ""}{r.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            The assignee always receives a notification. These are additional recipients.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Any additional notes or context..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={loading}
          className="flex items-center gap-2 bg-[#1e3a8a] hover:bg-[#1e40af] text-white font-semibold px-6 py-2.5 rounded-lg transition-colors disabled:opacity-60"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          {mode === "create" ? "Create Task" : "Save Changes"}
        </button>
        <button
          type="button"
          onClick={() => router.back()}
          className="px-5 py-2.5 text-sm text-gray-600 hover:text-gray-800 font-medium rounded-lg hover:bg-gray-100 transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
