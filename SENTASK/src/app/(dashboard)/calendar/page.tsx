"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Task } from "@/types";
import {
  format, startOfMonth, endOfMonth, startOfWeek, endOfWeek,
  eachDayOfInterval, isSameMonth, isSameDay, isToday,
  addMonths, subMonths, parseISO,
} from "date-fns";
import { ChevronLeft, ChevronRight, AlertCircle } from "lucide-react";
import { PRIORITY_CONFIG, STATUS_CONFIG, isOverdue } from "@/lib/utils";
import Link from "next/link";

export default function CalendarPage() {
  const [currentDate, setCurrentDate] = useState(new Date());

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
  const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start: calStart, end: calEnd });

  const { data } = useQuery<{ data: Task[] }>({
    queryKey: ["tasks", "calendar", format(currentDate, "yyyy-MM")],
    queryFn: async () => {
      const from = format(calStart, "yyyy-MM-dd");
      const to = format(calEnd, "yyyy-MM-dd");
      const res = await fetch(`/api/tasks?dueDateFrom=${from}&dueDateTo=${to}&pageSize=200`);
      return res.json();
    },
  });

  const tasks = data?.data || [];

  function getTasksForDay(day: Date): Task[] {
    return tasks.filter(
      (t) => t.dueDate && isSameDay(parseISO(t.dueDate), day)
    );
  }

  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900">{format(currentDate, "MMMM yyyy")}</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentDate(subMonths(currentDate, 1))}
            className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            <ChevronLeft className="w-4 h-4 text-gray-500" />
          </button>
          <button
            onClick={() => setCurrentDate(new Date())}
            className="px-3 py-1.5 text-sm font-medium border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-gray-600"
          >
            Today
          </button>
          <button
            onClick={() => setCurrentDate(addMonths(currentDate, 1))}
            className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
          >
            <ChevronRight className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </div>

      {/* Calendar grid */}
      <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
        {/* Day headers */}
        <div className="grid grid-cols-7 border-b border-gray-100">
          {WEEKDAYS.map((d) => (
            <div key={d} className="py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">
              {d}
            </div>
          ))}
        </div>

        {/* Days */}
        <div className="grid grid-cols-7">
          {days.map((day, idx) => {
            const dayTasks = getTasksForDay(day);
            const isCurrentMonth = isSameMonth(day, currentDate);
            const isCurrentDay = isToday(day);

            return (
              <div
                key={idx}
                className={`min-h-[100px] border-b border-r border-gray-50 p-2 ${
                  !isCurrentMonth ? "bg-gray-50/50" : ""
                } ${isCurrentDay ? "bg-blue-50/30" : ""}`}
              >
                <div className={`w-7 h-7 flex items-center justify-center rounded-full text-sm mb-1 ${
                  isCurrentDay
                    ? "bg-[#1e3a8a] text-white font-bold"
                    : isCurrentMonth
                    ? "text-gray-700 font-medium"
                    : "text-gray-300"
                }`}>
                  {format(day, "d")}
                </div>

                <div className="space-y-0.5">
                  {dayTasks.slice(0, 3).map((task) => {
                    const overdue = isOverdue(task.dueDate, task.status);
                    const p = PRIORITY_CONFIG[task.priority];
                    return (
                      <Link
                        key={task.id}
                        href={`/tasks/${task.id}`}
                        className={`flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full font-medium transition-opacity hover:opacity-80 ${p.bg} ${p.color}`}
                      >
                        {overdue && <AlertCircle className="w-3 h-3 flex-shrink-0" />}
                        <span className="truncate">{task.title}</span>
                      </Link>
                    );
                  })}
                  {dayTasks.length > 3 && (
                    <p className="text-xs text-gray-400 pl-1">+{dayTasks.length - 3} more</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-xs text-gray-500 font-medium">Priority:</span>
        {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5 text-xs">
            <span className={`px-2 py-0.5 rounded-full font-medium ${v.bg} ${v.color}`}>{v.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
