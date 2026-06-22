import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "EazziDoc — AI Medical Imaging",
  description:
    "AI-powered medical imaging diagnostics for underserved communities across Africa.",
  icons: {
    icon: "/icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 antialiased">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <AuthProvider>
            <Providers>{children}</Providers>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
