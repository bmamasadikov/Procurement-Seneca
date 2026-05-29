"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, CheckSquare, User2, Loader2, ArrowRight } from "lucide-react";
import { PRIORITY_CONFIG, STATUS_CONFIG } from "@/lib/utils";

interface SearchResult {
  tasks: Array<{
    id: string;
    title: string;
    status: string;
    priority: string;
    dueDate: string | null;
    assignee?: { id: string; name: string } | null;
  }>;
  users: Array<{
    id: string;
    name: string;
    email: string;
    jobTitle?: string | null;
    role: string;
  }>;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const allItems = [
    ...(results?.tasks || []).map((t) => ({ type: "task" as const, ...t })),
    ...(results?.users || []).map((u) => ({ type: "user" as const, ...u })),
  ];

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setResults(null);
    setActiveIdx(0);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") close();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  useEffect(() => {
    if (!query || query.length < 2) { setResults(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        setResults(await res.json());
        setActiveIdx(0);
      } finally {
        setLoading(false);
      }
    }, 200);
  }, [query]);

  function navigate(item: typeof allItems[number]) {
    if (item.type === "task") router.push(`/tasks/${item.id}`);
    else router.push(`/team`);
    close();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveIdx((i) => Math.min(i + 1, allItems.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActiveIdx((i) => Math.max(i - 1, 0)); }
    if (e.key === "Enter" && allItems[activeIdx]) navigate(allItems[activeIdx]);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={close} />
      <div className="relative w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden animate-fade-in">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <Search className="w-5 h-5 text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search tasks, people…"
            className="flex-1 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none bg-transparent"
          />
          {loading && <Loader2 className="w-4 h-4 animate-spin text-gray-400" />}
          <kbd className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded font-mono">ESC</kbd>
        </div>

        {/* Results */}
        {allItems.length > 0 && (
          <div className="max-h-80 overflow-y-auto py-2">
            {(results?.tasks.length ?? 0) > 0 && (
              <div>
                <p className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">Tasks</p>
                {results!.tasks.map((task, i) => {
                  const s = STATUS_CONFIG[task.status as keyof typeof STATUS_CONFIG];
                  const p = PRIORITY_CONFIG[task.priority as keyof typeof PRIORITY_CONFIG];
                  const idx = i;
                  return (
                    <button
                      key={task.id}
                      onClick={() => navigate({ type: "task", ...task })}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${activeIdx === idx ? "bg-blue-50" : "hover:bg-gray-50"}`}
                    >
                      <CheckSquare className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">{task.title}</p>
                        {task.assignee && (
                          <p className="text-xs text-gray-400 mt-0.5">{task.assignee.name}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${s?.bg} ${s?.color}`}>{s?.label}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ${p?.bg} ${p?.color}`}>{p?.label}</span>
                      </div>
                      <ArrowRight className="w-3.5 h-3.5 text-gray-300" />
                    </button>
                  );
                })}
              </div>
            )}
            {(results?.users.length ?? 0) > 0 && (
              <div>
                <p className="px-4 py-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wide">People</p>
                {results!.users.map((user, i) => {
                  const idx = (results?.tasks.length ?? 0) + i;
                  return (
                    <button
                      key={user.id}
                      onClick={() => navigate({ type: "user", ...user })}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${activeIdx === idx ? "bg-blue-50" : "hover:bg-gray-50"}`}
                    >
                      <User2 className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900">{user.name}</p>
                        <p className="text-xs text-gray-400">{user.email}</p>
                      </div>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded capitalize flex-shrink-0">
                        {user.role.toLowerCase()}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {query.length >= 2 && !loading && allItems.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-gray-400">
            No results for <span className="font-medium text-gray-600">"{query}"</span>
          </div>
        )}

        {!query && (
          <div className="px-4 py-5 text-center text-xs text-gray-400">
            Start typing to search tasks and people
          </div>
        )}

        <div className="border-t border-gray-50 px-4 py-2 flex items-center gap-4 text-xs text-gray-400">
          <span><kbd className="bg-gray-100 px-1 rounded font-mono">↑↓</kbd> navigate</span>
          <span><kbd className="bg-gray-100 px-1 rounded font-mono">↵</kbd> open</span>
          <span><kbd className="bg-gray-100 px-1 rounded font-mono">⌘K</kbd> toggle</span>
        </div>
      </div>
    </div>
  );
}
