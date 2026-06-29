"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { resetPassword } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <Card>
        <div className="text-center py-2">
          <p className="text-sm text-red-600 dark:text-red-400 mb-4">
            This reset link is missing or invalid. Please request a new one.
          </p>
          <Link
            href="/forgot-password"
            className="font-medium text-primary-600 hover:underline dark:text-primary-400 text-sm"
          >
            Request a new link →
          </Link>
        </div>
      </Card>
    );
  }

  if (done) {
    return (
      <Card>
        <div className="text-center py-2">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Password updated</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Your password has been changed successfully.
          </p>
          <Button onClick={() => router.push("/login")} className="w-full">
            Sign in with new password
          </Button>
        </div>
      </Card>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "This link has expired or is invalid. Please request a new one."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Set a new password</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
        Must be at least 8 characters with one uppercase letter and one digit.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <PasswordInput
          id="password"
          label="New password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
        />
        <PasswordInput
          id="confirm"
          label="Confirm password"
          placeholder="••••••••"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          autoComplete="new-password"
        />
        {error && (
          <p className="text-sm text-red-600 bg-red-50 dark:bg-red-950/30 rounded-lg px-3 py-2">{error}</p>
        )}
        <Button type="submit" loading={loading} className="w-full" size="lg">
          Update password
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
        <Link href="/login" className="font-medium text-primary-600 hover:underline dark:text-primary-400">
          Back to login
        </Link>
      </p>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
