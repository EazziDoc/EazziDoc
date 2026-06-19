"use client";

import {
  Activity,
  Calendar,
  FileText,
  Home,
  LogOut,
  Settings,
  Stethoscope,
  Upload,
  UserCheck,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

const patientLinks = [
  { href: "/patient", label: "Dashboard", icon: Home },
  { href: "/patient/upload", label: "Upload Images", icon: Upload },
  { href: "/patient/diagnoses", label: "My Diagnoses", icon: FileText },
  { href: "/patient/appointments", label: "Appointments", icon: Calendar },
  { href: "/patient/doctors", label: "Find a Doctor", icon: Stethoscope },
  { href: "/patient/settings", label: "Settings", icon: Settings },
];

const doctorLinks = [
  { href: "/doctor", label: "Dashboard", icon: Home },
  { href: "/doctor/queue", label: "Review Queue", icon: Stethoscope },
  { href: "/doctor/appointments", label: "Appointments", icon: Calendar },
  { href: "/doctor/patients", label: "My Patients", icon: UserCheck },
  { href: "/doctor/settings", label: "Settings", icon: Settings },
];

const adminLinks = [
  { href: "/admin", label: "Overview", icon: Home },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/diagnoses", label: "Diagnoses", icon: FileText },
  { href: "/admin/queue", label: "Queue health", icon: Activity },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const links =
    user?.role === "admin"
      ? adminLinks
      : user?.role === "doctor"
        ? doctorLinks
        : patientLinks;

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-gray-200 bg-white">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 border-b border-gray-100 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white text-sm font-bold">
          E
        </div>
        <span className="font-semibold text-gray-900">EazziDoc</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 overflow-y-auto p-4">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname === href || pathname.startsWith(href + "/")
                ? "bg-primary-50 text-primary-700"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* User */}
      <div className="border-t border-gray-100 p-4">
        <div className="mb-3 rounded-lg bg-gray-50 px-3 py-2">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            {user?.role}
          </p>
          <p className="text-sm text-gray-900 truncate">{user?.email}</p>
        </div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
