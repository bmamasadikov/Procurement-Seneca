"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TaskFilters, User, Department } from "@/types";
import { Search, SlidersHorizontal, X, Tag } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  BACKLOG: "Backlog",
  TODO: "To Do",
  IN_PROGRESS: "In Progress",
  WAITING: "Waiting",
  DONE: "Done",
};

const PRIORITY_LABELS: Record<string, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

interface TaskFiltersProps {
  filters: TaskFilters;
  onChange: (filters: TaskFilters) => void;
}

export function TaskFiltersBar({ filters, onChange }: TaskFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { data: users = [] } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: async () => (await fetch("/api/users")).json(),
  });

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: async () => (await fetch("/api/departments")).json(),
  });

  function update(key: keyof TaskFilters, value: string) {
    onChange({ ...filters, [key]: value });
  }

  const hasFilters = Object.values(filters).some((v) => v && v !== "");
  const advancedFilterCount = [
    filters.assigneeId, filters.departmentId, filters.repeatType,
    filters.dueDateFrom, (filters as any).tag,
  ].filter(Boolean).length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search tasks..."
            value={filters.search || ""}
            onChange={(e) => update("search", e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          />
        </div>

        {/* Status */}
        <select
          value={filters.status || ""}
          onChange={(e) => update("status", e.target.value)}
          className={`border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-28 transition-colors ${
            filters.status ? "border-blue-400 bg-blue-50 text-blue-700 font-medium" : "border-gray-200 bg-white"
          }`}
        >
          <option value="">All Status</option>
          <option value="BACKLOG">Backlog</option>
          <option value="TODO">To Do</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="WAITING">Waiting</option>
          <option value="DONE">Done</option>
        </select>

        {/* Priority */}
        <select
          value={filters.priority || ""}
          onChange={(e) => update("priority", e.target.value)}
          className={`border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-28 transition-colors ${
            filters.priority ? "border-orange-400 bg-orange-50 text-orange-700 font-medium" : "border-gray-200 bg-white"
          }`}
        >
          <option value="">All Priority</option>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
          <option value="LOW">Low</option>
        </select>

        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
            showAdvanced || advancedFilterCount > 0 ? "bg-blue-50 border-blue-300 text-blue-700" : "bg-white border-gray-200 text-gray-600 hover:border-gray-300"
          }`}
        >
          <SlidersHorizontal className="w-3.5 h-3.5" />
          Filters
          {advancedFilterCount > 0 && (
            <span className="bg-blue-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-4 text-center leading-none">
              {advancedFilterCount}
            </span>
          )}
        </button>

        {hasFilters && (
          <button
            onClick={() => onChange({})}
            className="flex items-center gap-1 px-3 py-2 rounded-lg border border-red-200 bg-red-50 text-red-600 text-sm font-medium hover:bg-red-100 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Active filter chips */}
      {(filters.status || filters.priority) && (
        <div className="flex flex-wrap gap-2">
          {filters.status && (
            <span className="flex items-center gap-1 text-xs bg-blue-100 text-blue-700 border border-blue-200 px-2.5 py-1 rounded-full font-medium">
              Status: {STATUS_LABELS[filters.status] || filters.status}
              <button
                onClick={() => update("status", "")}
                className="ml-0.5 hover:text-blue-900 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
          {filters.priority && (
            <span className="flex items-center gap-1 text-xs bg-orange-100 text-orange-700 border border-orange-200 px-2.5 py-1 rounded-full font-medium">
              Priority: {PRIORITY_LABELS[filters.priority] || filters.priority}
              <button
                onClick={() => update("priority", "")}
                className="ml-0.5 hover:text-orange-900 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          )}
        </div>
      )}

      {/* Advanced */}
      {showAdvanced && (
        <div className="flex flex-wrap gap-3 p-4 bg-gray-50 rounded-lg border border-gray-100">
          <select
            value={filters.assigneeId || ""}
            onChange={(e) => update("assigneeId", e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">Any Assignee</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>

          <select
            value={filters.departmentId || ""}
            onChange={(e) => update("departmentId", e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">Any Department</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>

          <select
            value={filters.repeatType || ""}
            onChange={(e) => update("repeatType", e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">Any Repeat</option>
            <option value="NONE">One-time</option>
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
          </select>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Due:</span>
            <input
              type="date"
              value={filters.dueDateFrom || ""}
              onChange={(e) => update("dueDateFrom", e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            />
            <span className="text-gray-400">→</span>
            <input
              type="date"
              value={filters.dueDateTo || ""}
              onChange={(e) => update("dueDateTo", e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            />
          </div>

          <div className="flex items-center gap-2">
            <Tag className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
            <input
              type="text"
              value={(filters as any).tag || ""}
              onChange={(e) => update("tag" as any, e.target.value)}
              placeholder="Filter by tag…"
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white w-36"
            />
          </div>
        </div>
      )}
    </div>
  );
}
