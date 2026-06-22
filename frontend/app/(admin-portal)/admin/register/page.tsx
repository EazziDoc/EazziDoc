"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { registerAdmin } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { PasswordInput } from "@/components/ui/input";

export default function AdminRegisterPage() {
  const router = useRouter();

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    confirm_password: "",
    invite_code: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(field: string) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirm_password) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await registerAdmin({
        first_name: form.first_name,
        last_name: form.last_name,
        email: form.email,
        password: form.password,
        invite_code: form.invite_code,
      });
      router.push("/admin/login?registered=1");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h2 className="text-lg font-semibold text-white mb-1">Create Admin Account</h2>
      <p className="text-sm text-gray-400 mb-6">
        An invite code is required. Contact an existing administrator to obtain one.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Field label="First name">
            <input
              type="text"
              value={form.first_name}
              onChange={set("first_name")}
              required
              placeholder="Jane"
              className={inputCls}
            />
          </Field>
          <Field label="Last name">
            <input
              type="text"
              value={form.last_name}
              onChange={set("last_name")}
              required
              placeholder="Doe"
              className={inputCls}
            />
          </Field>
        </div>

        <Field label="Email address">
          <input
            type="email"
            value={form.email}
            onChange={set("email")}
            required
            autoComplete="email"
            placeholder="admin@example.com"
            className={inputCls}
          />
        </Field>

        <Field label="Password">
          <PasswordInput
            value={form.password}
            onChange={set("password")}
            required
            autoComplete="new-password"
            placeholder="Min. 8 chars, 1 uppercase, 1 number"
            className="border-gray-700 bg-gray-800 text-white placeholder:text-gray-500 focus:border-primary-500 focus:ring-primary-500/20"
          />
        </Field>

        <Field label="Confirm password">
          <PasswordInput
            value={form.confirm_password}
            onChange={set("confirm_password")}
            required
            autoComplete="new-password"
            placeholder="Repeat password"
            className="border-gray-700 bg-gray-800 text-white placeholder:text-gray-500 focus:border-primary-500 focus:ring-primary-500/20"
          />
        </Field>

        <div className="border-t border-gray-800 pt-4">
          <Field label="Invite code">
            <input
              type="password"
              value={form.invite_code}
              onChange={set("invite_code")}
              required
              autoComplete="off"
              placeholder="••••••••••••"
              className={inputCls}
            />
          </Field>
        </div>

        {error && (
          <p className="text-sm text-red-400 bg-red-950/50 border border-red-800/50 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <Button type="submit" loading={loading} className="w-full" size="lg">
          Create account
        </Button>
      </form>

      <p className="mt-5 text-center text-sm text-gray-500">
        Already have an account?{" "}
        <Link href="/admin/login" className="text-gray-300 hover:text-white underline">
          Sign in
        </Link>
      </p>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-gray-300">{label}</label>
      {children}
    </div>
  );
}

const inputCls =
  "h-10 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 text-sm text-white placeholder:text-gray-500 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20";
