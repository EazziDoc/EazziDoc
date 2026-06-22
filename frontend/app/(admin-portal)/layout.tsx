import { ThemeToggle } from "@/components/ui/theme-toggle";

export default function AdminPortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-100 dark:bg-gray-950 flex items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-sm">E</span>
            </div>
            <span className="text-gray-900 dark:text-white font-semibold text-xl tracking-tight">EazziDoc</span>
          </div>
          <div className="inline-flex items-center gap-2 bg-amber-100 border border-amber-300 dark:bg-amber-950/50 dark:border-amber-700/40 rounded-full px-3 py-1">
            <div className="w-1.5 h-1.5 rounded-full bg-amber-500 dark:bg-amber-400 animate-pulse" />
            <span className="text-amber-700 dark:text-amber-400 text-xs font-semibold tracking-wide uppercase">
              Admin Portal
            </span>
          </div>
        </div>
        <div className="bg-white border border-gray-200 dark:bg-gray-900 dark:border-gray-800 rounded-2xl p-8 shadow-xl">
          {children}
        </div>
        <p className="mt-6 text-center text-xs text-gray-500 dark:text-gray-600">
          Not an admin?{" "}
          <a href="/login" className="text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-300 underline">
            Patient / Doctor login
          </a>
        </p>
      </div>
    </div>
  );
}
