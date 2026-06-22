import Image from "next/image";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-50 to-white dark:from-gray-950 dark:to-gray-900 flex items-center justify-center p-4">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Image
            src="/logo.png"
            alt="EazziDoc"
            width={160}
            height={53}
            className="object-contain mx-auto mb-3 dark:brightness-0 dark:invert"
          />
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            AI-powered medical diagnostics
          </p>
        </div>
        {children}
      </div>
    </div>
  );
}
