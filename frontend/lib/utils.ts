import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function statusColor(status: string) {
  const map: Record<string, string> = {
    pending: "bg-yellow-100 text-yellow-800",
    ai_complete: "bg-blue-100 text-blue-800",
    under_review: "bg-purple-100 text-purple-800",
    confirmed: "bg-green-100 text-green-800",
    completed: "bg-green-100 text-green-800",
    overridden: "bg-orange-100 text-orange-800",
    flagged: "bg-red-100 text-red-800",
    cancelled: "bg-gray-100 text-gray-600",
    booked: "bg-yellow-100 text-yellow-800",
  };
  return map[status] ?? "bg-gray-100 text-gray-600";
}
