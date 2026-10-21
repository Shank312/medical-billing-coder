"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiClientError, api } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md p-8">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-semibold text-slate-900">Medical Billing Coder</h1>
        <p className="mt-1 text-sm text-slate-500">Sign in to your coding workspace</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        {error ? <Alert variant="error">{error}</Alert> : null}

        <Input
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />

        <Input
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <Button type="submit" loading={loading} className="w-full">
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-slate-400">
        Phase 1 preview — registration and team management arrive next.
      </p>
    </Card>
  );
}
