"use client";

import Link from "next/link";
import { useState } from "react";
import { forgotPassword } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch {
      // Always show the success message to avoid leaking whether the email exists
      setSent(true);
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <Card>
        <div className="text-center py-2">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Check your email</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6 leading-relaxed">
            If an account exists for <strong>{email}</strong>, we&apos;ve sent a password reset link.
            It expires in 30 minutes.
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Didn&apos;t receive it? Check your spam folder, or{" "}
            <button
              className="text-primary-600 hover:underline dark:text-primary-400"
              onClick={() => setSent(false)}
            >
              try again
            </button>
            .
          </p>
        </div>
        <p className="mt-6 text-center text-sm text-gray-500 dark:text-gray-400">
          <Link href="/login" className="font-medium text-primary-600 hover:underline dark:text-primary-400">
            Back to login
          </Link>
        </p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Forgot your password?</h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
        Enter your account email and we&apos;ll send you a reset link.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          id="email"
          type="email"
          label="Email address"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
        />
        {error && (
          <p className="text-sm text-red-600 bg-red-50 dark:bg-red-950/30 rounded-lg px-3 py-2">{error}</p>
        )}
        <Button type="submit" loading={loading} className="w-full" size="lg">
          Send reset link
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
