import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, api } from "@/shared/api/client";
import type { User, VerifyState } from "@/shared/api/types";
import { useAuth } from "@/features/auth/AuthContext";
import { Field, FormAlert } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { useTitle } from "@/shared/lib/dom";

/** Only same-site paths are allowed as ?next= targets. */
export function safeNext(next: string | null) {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export default function SignIn() {
  useTitle("Sign in");
  const { user, setUser } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [form, setForm] = useState({ username: "", password: "", remember: true });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (user) navigate(next, { replace: true }); }, [user, next, navigate]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const r = await api<{ user: User }>("/api/auth/sign-in/", { method: "POST", body: form });
      toast("You're signed in.", "success");
      setUser(r.user);
    } catch (ex) {
      if (ex instanceof ApiError && ex.status === 403 && ex.data.verify) {
        toast("Verify your email to finish setting up your account. We've sent you a new code.", "info");
        navigate("/accounts/verify", { state: { verify: ex.data.verify as VerifyState, next } });
        return;
      }
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Sign in</h1>
      <p className="auth-lead">Use your GEIDA account to run analyses, save project areas and generate reports.</p>
      <FormAlert text={err} />
      <form className="form" noValidate onSubmit={submit}>
        <Field label="Email or username" autoComplete="username" autoFocus placeholder="name@isdb.org"
          value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <Field label="Password" type="password" autoComplete="current-password"
          aside={<Link className="field-link" to="/accounts/password-reset">Forgot password?</Link>}
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <label className="check">
          <input type="checkbox" className="checkbox" checked={form.remember} onChange={(e) => setForm({ ...form, remember: e.target.checked })} />
          <span>Keep me signed in</span>
        </label>
        <button className="btn btn-dark btn-block" type="submit" disabled={busy}>Sign in</button>
      </form>
      <p className="auth-switch">New to GEIDA? <Link to="/accounts/register">Create an account</Link></p>
    </>
  );
}
