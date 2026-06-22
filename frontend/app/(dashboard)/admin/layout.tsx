"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AdminSectionLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && user.role !== "admin") {
      router.replace("/admin/login");
    }
  }, [user, loading, router]);

  if (loading || !user || user.role !== "admin") return null;

  return <>{children}</>;
}
