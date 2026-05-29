"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import toast from "react-hot-toast";
import { TaskTemplate, Department, GoogleWorkspaceSettings } from "@/types";
import { Plus, X, Loader2, Building2, LayoutTemplate, Calendar, Mail, ShieldCheck, Cloud, RefreshCw, Send, Link2, CheckCircle2, AlertCircle } from "lucide-react";

export default function SettingsPage() {
  const { data: session } = useSession();
  if (session?.user?.role !== "ADMIN") redirect("/dashboard");

  return (
    <div className="space-y-6 animate-fade-in max-w-4xl">
      <GoogleWorkspaceSection />
      <TelegramSection />
      <TemplateSettings />
      <DepartmentSettings />
    </div>
  );
}

function GoogleWorkspaceSection() {
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);

  const { data: settings } = useQuery<GoogleWorkspaceSettings>({
    queryKey: ["google-workspace-settings"],
    queryFn: async () => {
      const res = await fetch("/api/settings/google-workspace");
      if (!res.ok) throw new Error("Failed to load Google Workspace settings");
      return res.json();
    },
  });

  const [allowedDomains, setAllowedDomains] = useState("");
  const [defaultSenderEmail, setDefaultSenderEmail] = useState("");
  const [defaultCalendarId, setDefaultCalendarId] = useState("primary");
  const [reminderMinutesBefore, setReminderMinutesBefore] = useState(30);
  const [gmailSendingMode, setGmailSendingMode] = useState<"SMTP" | "GMAIL_API">("GMAIL_API");
  const [calendarCompletionBehavior, setCalendarCompletionBehavior] = useState<"KEEP" | "MARK_DONE" | "DELETE">("MARK_DONE");
  const [autoProvisionUsers, setAutoProvisionUsers] = useState(true);
  const [adminApprovalRequired, setAdminApprovalRequired] = useState(true);
  const [calendarSyncEnabled, setCalendarSyncEnabled] = useState(true);
  const [defaultCreateCalendarEvents, setDefaultCreateCalendarEvents] = useState(false);
  const [directorySyncEnabled, setDirectorySyncEnabled] = useState(true);
  const [driveAttachmentsEnabled, setDriveAttachmentsEnabled] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setAllowedDomains(settings.allowedDomains.join(", "));
    setDefaultSenderEmail(settings.defaultSenderEmail);
    setDefaultCalendarId(settings.defaultCalendarId);
    setReminderMinutesBefore(settings.reminderMinutesBefore);
    setGmailSendingMode(settings.gmailSendingMode);
    setCalendarCompletionBehavior(settings.calendarCompletionBehavior);
    setAutoProvisionUsers(settings.autoProvisionUsers);
    setAdminApprovalRequired(settings.adminApprovalRequired);
    setCalendarSyncEnabled(settings.calendarSyncEnabled);
    setDefaultCreateCalendarEvents(settings.defaultCreateCalendarEvents);
    setDirectorySyncEnabled(settings.directorySyncEnabled);
    setDriveAttachmentsEnabled(settings.driveAttachmentsEnabled);
  }, [settings]);

  async function saveSettings() {
    setSaving(true);
    try {
      const res = await fetch("/api/settings/google-workspace", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          allowedDomains: allowedDomains.split(",").map((domain) => domain.trim()).filter(Boolean),
          defaultSenderEmail,
          defaultCalendarId,
          reminderMinutesBefore: Number(reminderMinutesBefore),
          gmailSendingMode,
          calendarCompletionBehavior,
          autoProvisionUsers,
          adminApprovalRequired,
          calendarSyncEnabled,
          defaultCreateCalendarEvents,
          directorySyncEnabled,
          driveAttachmentsEnabled,
        }),
      });
      if (!res.ok) throw new Error("Failed to save Google Workspace settings");
      await queryClient.invalidateQueries({ queryKey: ["google-workspace-settings"] });
      toast.success("Google Workspace settings saved");
    } catch (error: any) {
      toast.error(error.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  async function syncDirectoryNow() {
    try {
      const res = await fetch("/api/google-workspace/directory/sync", {
        method: "POST",
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Directory sync failed");
      toast.success(`Directory synced: ${body.synced} users`);
    } catch (error: any) {
      toast.error(error.message || "Directory sync failed");
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cloud className="w-4 h-4 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Google Workspace</h3>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge label="OAuth Client" active={Boolean(settings?.googleClientConfigured)} />
          <StatusBadge label="Service Account" active={Boolean(settings?.googleServiceAccountConfigured)} />
        </div>
      </div>

      <div className="p-5 space-y-6">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          OAuth client secrets and service account keys should stay in environment variables or a
          secret manager. This page stores non-secret Workspace behavior only.
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Allowed Google domains" icon={<ShieldCheck className="w-4 h-4" />}>
            <input
              type="text"
              value={allowedDomains}
              onChange={(e) => setAllowedDomains(e.target.value)}
              placeholder="seneca.uz"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-400">Comma-separated Workspace domains allowed to sign in.</p>
          </Field>

          <Field label="Default sender email" icon={<Mail className="w-4 h-4" />}>
            <input
              type="email"
              value={defaultSenderEmail}
              onChange={(e) => setDefaultSenderEmail(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </Field>

          <Field label="Gmail sending mode" icon={<Mail className="w-4 h-4" />}>
            <select
              value={gmailSendingMode}
              onChange={(e) => setGmailSendingMode(e.target.value as "SMTP" | "GMAIL_API")}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="GMAIL_API">Gmail API</option>
              <option value="SMTP">SMTP relay</option>
            </select>
          </Field>

          <Field label="Default Calendar ID" icon={<Calendar className="w-4 h-4" />}>
            <input
              type="text"
              value={defaultCalendarId}
              onChange={(e) => setDefaultCalendarId(e.target.value)}
              placeholder="primary"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </Field>

          <Field label="Reminder lead time (minutes)" icon={<Calendar className="w-4 h-4" />}>
            <input
              type="number"
              min={5}
              max={10080}
              value={reminderMinutesBefore}
              onChange={(e) => setReminderMinutesBefore(Number(e.target.value))}
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </Field>

          <Field label="Completed task calendar behavior" icon={<RefreshCw className="w-4 h-4" />}>
            <select
              value={calendarCompletionBehavior}
              onChange={(e) =>
                setCalendarCompletionBehavior(e.target.value as "KEEP" | "MARK_DONE" | "DELETE")
              }
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value="MARK_DONE">Keep event and mark done</option>
              <option value="KEEP">Keep event unchanged</option>
              <option value="DELETE">Delete event</option>
            </select>
          </Field>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <ToggleCard
            title="Auto-provision Google users"
            description="Create a SENTASK user record the first time an allowed Workspace user signs in."
            checked={autoProvisionUsers}
            onChange={setAutoProvisionUsers}
          />
          <ToggleCard
            title="Require admin approval"
            description="New Google Workspace users land in PENDING until an admin assigns their role."
            checked={adminApprovalRequired}
            onChange={setAdminApprovalRequired}
          />
          <ToggleCard
            title="Enable Calendar sync"
            description="Allow tasks to create and update Google Calendar events."
            checked={calendarSyncEnabled}
            onChange={setCalendarSyncEnabled}
          />
          <ToggleCard
            title="Default task Calendar sync"
            description="New tasks will start with Google Calendar sync enabled."
            checked={defaultCreateCalendarEvents}
            onChange={setDefaultCreateCalendarEvents}
          />
          <ToggleCard
            title="Enable directory sync"
            description="Use Admin SDK directory sync so task assignees match real Workspace accounts."
            checked={directorySyncEnabled}
            onChange={setDirectorySyncEnabled}
          />
          <ToggleCard
            title="Enable Drive attachment mode"
            description="Prepares attachment architecture for future Google Drive-backed storage."
            checked={driveAttachmentsEnabled}
            onChange={setDriveAttachmentsEnabled}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={saveSettings}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-[#1e3a8a] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#1e40af] disabled:opacity-60"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Cloud className="w-4 h-4" />}
            Save Workspace Settings
          </button>

          <button
            type="button"
            onClick={syncDirectoryNow}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
          >
            <RefreshCw className="w-4 h-4" />
            Sync Directory Now
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  icon,
  children,
}: {
  label: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 flex items-center gap-2 text-sm font-medium text-gray-700">
        <span className="text-blue-600">{icon}</span>
        {label}
      </label>
      {children}
    </div>
  );
}

function ToggleCard({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-gray-100 p-4">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-1 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
      />
      <div>
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <p className="mt-1 text-xs text-gray-500">{description}</p>
      </div>
    </label>
  );
}

function StatusBadge({ label, active }: { label: string; active: boolean }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"
      }`}
    >
      {label}: {active ? "Configured" : "Missing"}
    </span>
  );
}

function TelegramSection() {
  const [loading, setLoading] = useState(false);
  const [groupChatId, setGroupChatId] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");

  const { data: settings, refetch } = useQuery({
    queryKey: ["telegram-settings"],
    queryFn: async () => {
      const res = await fetch("/api/settings/telegram");
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
  });

  useEffect(() => {
    if (!settings) return;
    setGroupChatId(settings.groupChatId || "");
    setWebhookSecret(settings.webhookSecret || "");
  }, [settings]);

  async function save() {
    setLoading(true);
    try {
      const res = await fetch("/api/settings/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "save", groupChatId, webhookSecret }),
      });
      if (!res.ok) throw new Error("Failed");
      toast.success("Telegram settings saved");
      refetch();
    } catch { toast.error("Failed to save"); }
    finally { setLoading(false); }
  }

  async function doAction(action: string) {
    setLoading(true);
    try {
      const res = await fetch("/api/settings/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed");
      if (action === "setWebhook") toast.success(`Webhook registered: ${data.webhookUrl}`);
      if (action === "deleteWebhook") toast.success("Webhook removed");
      if (action === "testMessage") toast.success("Test message sent to group!");
      refetch();
    } catch (err: any) { toast.error(err.message || "Failed"); }
    finally { setLoading(false); }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-5">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 bg-sky-50 rounded-xl flex items-center justify-center flex-shrink-0">
          <Send className="w-4 h-4 text-sky-500" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-gray-900">Telegram Group Integration</h2>
          <p className="text-xs text-gray-500 mt-0.5">Send all task notifications to a Telegram group and allow marking tasks done from chat</p>
        </div>
      </div>

      {/* Bot token status */}
      <div className={`flex items-center gap-2 text-xs px-3 py-2 rounded-lg border ${settings?.botTokenConfigured ? "bg-green-50 border-green-200 text-green-700" : "bg-amber-50 border-amber-200 text-amber-700"}`}>
        {settings?.botTokenConfigured
          ? <><CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" /> Bot token configured via <code className="font-mono bg-green-100 px-1 rounded">TELEGRAM_BOT_TOKEN</code> environment variable</>
          : <><AlertCircle className="w-3.5 h-3.5 flex-shrink-0" /> <span><code className="font-mono bg-amber-100 px-1 rounded">TELEGRAM_BOT_TOKEN</code> not set — create a bot via @BotFather and add to your <code className="font-mono bg-amber-100 px-1 rounded">.env</code></span></>
        }
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Group Chat ID
            <span className="text-xs text-gray-400 font-normal ml-1.5">— from @username_to_id_bot or bot messages</span>
          </label>
          <input
            type="text"
            value={groupChatId}
            onChange={(e) => setGroupChatId(e.target.value)}
            placeholder="-1001234567890"
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
          <p className="text-xs text-gray-400 mt-1">Add the bot to your group, then get its ID. Group IDs are usually negative numbers.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">
            Webhook Secret
            <span className="text-xs text-gray-400 font-normal ml-1.5">— used to verify Telegram requests</span>
          </label>
          <input
            type="text"
            value={webhookSecret}
            onChange={(e) => setWebhookSecret(e.target.value)}
            placeholder="random-secret-string"
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
          <p className="text-xs text-gray-400 mt-1">Generate any random string. Telegram will include it in every webhook call.</p>
        </div>
      </div>

      {/* Webhook URL */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5 flex items-center gap-1.5">
          <Link2 className="w-3.5 h-3.5 text-gray-400" />
          Webhook URL
        </label>
        <div className="flex gap-2 items-center">
          <code className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-600 font-mono truncate">
            {settings?.webhookUrl || "—"}
          </code>
        </div>
        {settings?.currentWebhook && (
          <p className="text-xs text-green-600 mt-1">
            ✓ Currently registered: <span className="font-mono">{settings.currentWebhook}</span>
          </p>
        )}
      </div>

      <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
        <button
          onClick={save}
          disabled={loading}
          className="flex items-center gap-1.5 px-4 py-2 bg-[#1e3a8a] hover:bg-[#1e40af] text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
          Save Settings
        </button>
        <button
          onClick={() => doAction("setWebhook")}
          disabled={loading || !settings?.botTokenConfigured}
          className="flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <Link2 className="w-4 h-4" />
          Register Webhook
        </button>
        <button
          onClick={() => doAction("testMessage")}
          disabled={loading || !groupChatId}
          className="flex items-center gap-1.5 px-4 py-2 border border-green-300 text-green-700 bg-green-50 hover:bg-green-100 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <Send className="w-4 h-4" />
          Send Test Message
        </button>
        <button
          onClick={() => doAction("deleteWebhook")}
          disabled={loading || !settings?.botTokenConfigured}
          className="flex items-center gap-1.5 px-4 py-2 border border-red-200 text-red-600 bg-red-50 hover:bg-red-100 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
        >
          <X className="w-4 h-4" />
          Remove Webhook
        </button>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs text-gray-600 space-y-1">
        <p className="font-semibold text-gray-700">Setup steps:</p>
        <p>1. Create a bot via <strong>@BotFather</strong> in Telegram → copy token to <code className="font-mono bg-gray-100 px-1 rounded">TELEGRAM_BOT_TOKEN</code> env var</p>
        <p>2. Add your bot to the target group and make it an <strong>admin</strong></p>
        <p>3. Get the group chat ID (forward a group message to <strong>@userinfobot</strong>)</p>
        <p>4. Enter the Group Chat ID above and click <strong>Save Settings</strong></p>
        <p>5. Set <code className="font-mono bg-gray-100 px-1 rounded">APP_URL</code> env var to your public domain (e.g. https://tasks.seneca.uz)</p>
        <p>6. Click <strong>Register Webhook</strong> — Telegram will now POST updates to SENTASK</p>
        <p>7. Members can reply to notifications in the group to add comments, or press <strong>✅ Mark Done</strong></p>
      </div>
    </div>
  );
}

function TemplateSettings() {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const { data: templates = [] } = useQuery<TaskTemplate[]>({
    queryKey: ["templates"],
    queryFn: async () => (await fetch("/api/templates")).json(),
  });

  async function addTemplate() {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      const res = await fetch("/api/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), description: newDesc }),
      });
      if (!res.ok) throw new Error("Failed");
      toast.success("Template added");
      setNewName("");
      setNewDesc("");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["templates"] });
    } catch {
      toast.error("Failed to add template");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LayoutTemplate className="w-4 h-4 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Task Templates</h3>
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{templates.length}</span>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Template
        </button>
      </div>

      {showForm && (
        <div className="px-5 py-4 bg-blue-50/50 border-b border-blue-100">
          <div className="flex gap-3">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Template name"
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optional)"
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={addTemplate}
              disabled={adding || !newName.trim()}
              className="flex items-center gap-1.5 bg-[#1e3a8a] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
            >
              {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              Add
            </button>
            <button onClick={() => setShowForm(false)} className="p-2 text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-gray-50">
        {templates.map((t) => (
          <div key={t.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50/50 transition-colors">
            <div>
              <p className="text-sm font-medium text-gray-900">{t.name}</p>
              {t.description && <p className="text-xs text-gray-400 mt-0.5">{t.description}</p>}
            </div>
            <div className="flex items-center gap-2">
              {t.isSystem && (
                <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">System</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function DepartmentSettings() {
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newColor, setNewColor] = useState("#1e3a8a");
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const { data: departments = [] } = useQuery<(Department & { _count: any })[]>({
    queryKey: ["departments"],
    queryFn: async () => (await fetch("/api/departments")).json(),
  });

  async function addDepartment() {
    if (!newName.trim()) return;
    setAdding(true);
    try {
      const res = await fetch("/api/departments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), color: newColor }),
      });
      if (!res.ok) throw new Error("Failed");
      toast.success("Department added");
      setNewName("");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["departments"] });
    } catch {
      toast.error("Failed to add department");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-blue-600" />
          <h3 className="font-semibold text-gray-900">Departments</h3>
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{departments.length}</span>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Department
        </button>
      </div>

      {showForm && (
        <div className="px-5 py-4 bg-blue-50/50 border-b border-blue-100">
          <div className="flex gap-3">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Department name"
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">Color</label>
              <input
                type="color"
                value={newColor}
                onChange={(e) => setNewColor(e.target.value)}
                className="w-10 h-9 rounded border border-gray-200 cursor-pointer"
              />
            </div>
            <button
              onClick={addDepartment}
              disabled={adding || !newName.trim()}
              className="flex items-center gap-1.5 bg-[#1e3a8a] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-60"
            >
              {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              Add
            </button>
            <button onClick={() => setShowForm(false)} className="p-2 text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      <div className="divide-y divide-gray-50">
        {departments.map((d) => (
          <div key={d.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50/50 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: d.color }} />
              <p className="text-sm font-medium text-gray-900">{d.name}</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span>{d._count?.users ?? 0} members</span>
              <span>{d._count?.tasks ?? 0} tasks</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
