import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";

interface StatsCardProps {
  label: string;
  value: number;
  icon: LucideIcon;
  color: "blue" | "yellow" | "green" | "red" | "purple" | "gray" | "orange";
  href?: string;
  subtitle?: string;
  suffix?: string;
}

const colorMap = {
  blue: {
    bg: "bg-blue-50",
    icon: "bg-blue-100 text-blue-600",
    text: "text-blue-700",
    border: "border-blue-100",
    value: "text-blue-900",
  },
  yellow: {
    bg: "bg-amber-50",
    icon: "bg-amber-100 text-amber-600",
    text: "text-amber-700",
    border: "border-amber-100",
    value: "text-amber-900",
  },
  green: {
    bg: "bg-emerald-50",
    icon: "bg-emerald-100 text-emerald-600",
    text: "text-emerald-700",
    border: "border-emerald-100",
    value: "text-emerald-900",
  },
  red: {
    bg: "bg-red-50",
    icon: "bg-red-100 text-red-600",
    text: "text-red-700",
    border: "border-red-100",
    value: "text-red-900",
  },
  purple: {
    bg: "bg-purple-50",
    icon: "bg-purple-100 text-purple-600",
    text: "text-purple-700",
    border: "border-purple-100",
    value: "text-purple-900",
  },
  gray: {
    bg: "bg-gray-50",
    icon: "bg-gray-100 text-gray-500",
    text: "text-gray-600",
    border: "border-gray-100",
    value: "text-gray-900",
  },
  orange: {
    bg: "bg-orange-50",
    icon: "bg-orange-100 text-orange-600",
    text: "text-orange-700",
    border: "border-orange-100",
    value: "text-orange-900",
  },
};

export function StatsCard({ label, value, icon: Icon, color, subtitle, suffix }: StatsCardProps) {
  const c = colorMap[color];
  return (
    <div className={cn("rounded-xl border p-5 flex items-start gap-4 hover:shadow-md transition-all bg-white", c.border)}>
      <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0", c.icon)}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">
          {value.toLocaleString()}
          {suffix && <span className="text-lg font-semibold ml-0.5">{suffix}</span>}
        </p>
        <p className="text-sm text-gray-500 mt-0.5">{label}</p>
        {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
      </div>
    </div>
  );
}
