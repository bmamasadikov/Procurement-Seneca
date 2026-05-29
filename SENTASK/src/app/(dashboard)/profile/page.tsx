"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import toast from "react-hot-toast";
import {
  User2, Mail, Phone, Briefcase, Bell, Lock,
  CheckCircle2, Building2, LogIn, Calendar, Loader2,
} from "lucide-react";
import { formatDateTime } from "@/lib/utils";

export default function ProfilePage() {
  const { data: session } = useSession();
  const queryClient = useQueryClient();

  const { data: profile, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: async () => {
      const res = await fetch("/api/profile");
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
  });

  const [name, setName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [phone, setPhone] = useState("");
  const [notifyByEmail, setNotifyByEmail] = useState(true);
  const [notifyByTelegram, setNotifyByTelegram] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Sync form state when profile loads
  const [loaded, setLoaded] = useState(false);
  if (profile && !loaded) {
    setName(profile.name || "");
    setJobTitle(profile.jobTitle || "");
    setPhone(profile.phone || "");
    setNotifyByEmail(profile.notifyByEmail ?? true);
    setNotifyByTelegram(profile.notifyByTelegram ?? false);
    setLoaded(true);
  }

  const updateProfile = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, jobTitle: jobTitle || null, phone: phone || null, notifyByEmail, notifyByTelegram }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast.success("Profile updated");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const changePassword = useMutation({
    mutationFn: async () => {
      if (newPassword !== confirmPassword) throw new Error("Passwords do not match");
      if (newPassword.length < 8) throw new Error("Password must be at least 8 characters");
      const res = await fetch("/api/profile/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword, newPassword }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed");
      }
      return res.json();
    },
    onSuccess: () => {
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success("Password changed successfully");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!profile) return null;

  const isGoogleUser = profile.authProvider === "GOOGLE";

  return (
    <div className="max-w-3xl animate-fade-in">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-900">My Profile</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your account settings and notification preferences.</p>
      </div>

      <div className="space-y-5">
        {/* Avatar + stats row */}
        <div className="bg-white rounded-xl border border-gray-100 p-5 flex items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-[#1e3a8a] flex items-center justify-center text-white text-2xl font-bold flex-shrink-0">
            {profile.name?.charAt(0)?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-lg font-semibold text-gray-900 truncate">{profile.name}</p>
            <p className="text-sm text-gray-500">{profile.email}</p>
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                profile.role === "ADMIN" ? "bg-purple-100 text-purple-700" :
                profile.role === "MANAGER" ? "bg-blue-100 text-blue-700" :
                "bg-gray-100 text-gray-600"
              }`}>
                {profile.role}
              </span>
              {profile.department && (
                <span className="text-xs text-gray-500 flex items-center gap-1">
                  <Building2 className="w-3 h-3" />
                  {profile.department.name}
                </span>
              )}
            </div>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-2xl font-bold text-gray-900">{profile._count?.assignedTasks ?? 0}</div>
            <div className="text-xs text-gray-500">tasks assigned</div>
          </div>
        </div>

        {/* Edit profile */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <User2 className="w-4 h-4 text-gray-400" />
            Personal Information
          </h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1 flex items-center gap-1">
                  <Briefcase className="w-3 h-3" /> Job Title
                </label>
                <input
                  type="text"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="e.g. Project Manager"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1 flex items-center gap-1">
                  <Phone className="w-3 h-3" /> Phone
                </label>
                <input
                  type="text"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+998 90 000 00 00"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Notification preferences */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Bell className="w-4 h-4 text-gray-400" />
            Notification Preferences
          </h2>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                onClick={() => setNotifyByEmail((v) => !v)}
                className={`w-10 h-5 rounded-full relative transition-colors ${notifyByEmail ? "bg-blue-600" : "bg-gray-200"}`}
              >
                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${notifyByEmail ? "translate-x-5" : "translate-x-0.5"}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Email notifications</p>
                <p className="text-xs text-gray-500">Receive task updates via email at {profile.email}</p>
              </div>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <div
                onClick={() => setNotifyByTelegram((v) => !v)}
                className={`w-10 h-5 rounded-full relative transition-colors ${notifyByTelegram ? "bg-blue-600" : "bg-gray-200"}`}
              >
                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${notifyByTelegram ? "translate-x-5" : "translate-x-0.5"}`} />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Telegram notifications</p>
                <p className="text-xs text-gray-500">
                  {profile.isTelegramLinked
                    ? `Linked as @${profile.telegramUsername}`
                    : "Telegram not linked yet — contact admin to set up"}
                </p>
              </div>
            </label>
          </div>
        </div>

        {/* Save button */}
        <div className="flex justify-end">
          <button
            onClick={() => updateProfile.mutate()}
            disabled={updateProfile.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#1e3a8a] hover:bg-[#1e40af] text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-60"
          >
            {updateProfile.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Save Changes
          </button>
        </div>

        {/* Change password — only for credentials users */}
        {!isGoogleUser && (
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Lock className="w-4 h-4 text-gray-400" />
              Change Password
            </h2>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Current Password</label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">New Password</label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Confirm New Password</label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  onClick={() => changePassword.mutate()}
                  disabled={changePassword.isPending || !currentPassword || !newPassword || !confirmPassword}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-900 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                >
                  {changePassword.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Update Password
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Account info */}
        <div className="bg-white rounded-xl border border-gray-100 p-5">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-gray-400" />
            Account Info
          </h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500 flex items-center gap-1.5"><Mail className="w-3.5 h-3.5" /> Email</span>
              <span className="font-medium text-gray-900">{profile.email}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Auth provider</span>
              <span className="font-medium text-gray-900 capitalize">{profile.authProvider?.toLowerCase()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500 flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> Member since</span>
              <span className="font-medium text-gray-900">{formatDateTime(profile.createdAt)}</span>
            </div>
            {profile.lastLoginAt && (
              <div className="flex justify-between">
                <span className="text-gray-500 flex items-center gap-1.5"><LogIn className="w-3.5 h-3.5" /> Last login</span>
                <span className="font-medium text-gray-900">{formatDateTime(profile.lastLoginAt)}</span>
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
}
