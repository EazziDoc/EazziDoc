"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { login, register } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login: authLogin } = useAuth();

  const [role, setRole] = useState<"patient" | "doctor">(
    params.get("role") === "doctor" ? "doctor" : "patient",
  );
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
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
    setLoading(true);
    try {
      await register({ ...form, role });
      const { access_token } = await login(form.email, form.password);
      await authLogin(access_token);
      router.push(role === "doctor" ? "/doctor" : "/patient");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">Create account</h2>

      {/* Role toggle */}
      <div className="flex rounded-lg border border-gray-200 p-1 mb-6">
        {(["patient", "doctor"] as const).map((r) => (
          <button
            key={r}
            type="button"
            onClick={() => setRole(r)}
            className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors capitalize ${
              role === r
                ? "bg-primary-600 text-white"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {r}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input
            id="first_name"
            label="First name"
            placeholder="Ada"
            value={form.first_name}
            onChange={set("first_name")}
            required
          />
          <Input
            id="last_name"
            label="Last name"
            placeholder="Obi"
            value={form.last_name}
            onChange={set("last_name")}
            required
          />
        </div>
        <Input
          id="email"
          type="email"
          label="Email address"
          placeholder="you@example.com"
          value={form.email}
          onChange={set("email")}
          required
          autoComplete="email"
        />
        <Input
          id="password"
          type="password"
          label="Password"
          placeholder="Min 8 chars, 1 uppercase, 1 digit"
          value={form.password}
          onChange={set("password")}
          required
          autoComplete="new-password"
        />
        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}
        <Button type="submit" loading={loading} className="w-full" size="lg">
          Create account
        </Button>
      </form>

      <p className="mt-4 text-center text-sm text-gray-500">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary-600 hover:underline">
          Sign in
        </Link>
      </p>
    </Card>
  );
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
