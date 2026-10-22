"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

export function LoginForm() {
  const router = useRouter();
  const { login, status } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/encounters");
    }
  }, [status, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/encounters");
    } catch (err) {
      setError(
        err instanceof ApiClientError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full max-w-md p-8">
      <div className="mb-6 flex flex-col items-center text-center">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent-600 text-white shadow-sm"
          aria-hidden="true"
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth={2.2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5.5v13m-6.5-6.5h13" />
          </svg>
        </div>
        <h1 className="mt-3 text-xl font-semibold tracking-tight text-ink">Medical Billing Coder</h1>
        <p className="mt-1 text-sm text-ink-muted">Sign in to your coding workspace</p>
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
    </Card>
  );
}
