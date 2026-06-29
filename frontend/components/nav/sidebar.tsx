"use client";

import {
  Activity,
  Calendar,
  ClipboardList,
  FileText,
  HelpCircle,
  Home,
  LogOut,
  Settings,
  ShieldCheck,
  Stethoscope,
  Upload,
  UserCheck,
  Users,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { cn } from "@/lib/utils";

const patientLinks = [
  { href: "/patient", label: "Dashboard", icon: Home },
  { href: "/patient/upload", label: "Upload Images", icon: Upload },
  { href: "/patient/diagnoses", label: "My Diagnoses", icon: FileText },
  { href: "/patient/appointments", label: "Appointments", icon: Calendar },
  { href: "/patient/doctors", label: "Find a Doctor", icon: Stethoscope },
  { href: "/patient/settings", label: "Settings", icon: Settings },
  { href: "/patient/support", label: "Contact Support", icon: HelpCircle },
];

const doctorLinks = [
  { href: "/doctor", label: "Dashboard", icon: Home },
  { href: "/doctor/queue", label: "Review Queue", icon: Stethoscope },
  { href: "/doctor/appointments", label: "Appointments", icon: Calendar },
  { href: "/doctor/patients", label: "My Patients", icon: UserCheck },
  { href: "/doctor/settings", label: "Settings", icon: Settings },
  { href: "/doctor/support", label: "Contact Support", icon: HelpCircle },
];

const adminLinks = [
  { href: "/admin", label: "Overview", icon: Home },
  { href: "/admin/users", label: "Users", icon: Users },
  { href: "/admin/doctors", label: "Doctor registrations", icon: ShieldCheck },
  { href: "/admin/diagnoses", label: "Diagnoses", icon: FileText },
  { href: "/admin/queue", label: "Queue health", icon: Activity },
  { href: "/admin/audit-logs", label: "Audit logs", icon: ClipboardList },
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
    <aside className="flex h-screen w-60 flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
      {/* Logo */}
      <div className="flex h-16 items-center border-b border-gray-100 px-4 dark:border-gray-800">
        <Image src="/logo.png" alt="EazziDoc" width={120} height={40} className="object-contain dark:brightness-0 dark:invert" />
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
                ? "bg-primary-50 text-primary-700 dark:bg-primary-950/40 dark:text-primary-400"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* User + theme toggle */}
      <div className="border-t border-gray-100 p-4 dark:border-gray-800">
        <div className="mb-3 rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-800">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide dark:text-gray-400">
            {user?.role}
          </p>
          <p className="text-sm text-gray-900 truncate dark:text-gray-100">{user?.email}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleLogout}
            className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-red-50 hover:text-red-600 dark:text-gray-400 dark:hover:bg-red-950/30 dark:hover:text-red-400 transition-colors"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
