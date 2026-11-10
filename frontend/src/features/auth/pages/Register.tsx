import { Check, CircleAlert } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, api } from "@/shared/api/client";
import type { VerifyState } from "@/shared/api/types";
import { useAuth } from "@/features/auth/AuthContext";
import { Field, FormAlert } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { useTitle } from "@/shared/lib/dom";

const EMPTY = { first_name: "", last_name: "", email: "", password1: "", password2: "", accept: false };

export function Steps({ step }: { step: 1 | 2 }) {
  return (
    <ol className="steps" aria-label="Account setup">
      <li className={step === 1 ? "is-current" : "is-done"} aria-current={step === 1 ? "step" : undefined}><span>{step === 1 ? 1 : <Check aria-hidden="true" />}</span>Your details</li>
      <li className={step === 2 ? "is-current" : ""} aria-current={step === 2 ? "step" : undefined}><span>2</span>Verify email</li>
    </ol>
  );
}

export default function Register() {
  useTitle("Create account");
  const { user } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  useEffect(() => { if (user) navigate("/", { replace: true }); }, [user, navigate]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null); setErrors({});
    try {
      const r = await api<{ verify: VerifyState; email_failed: boolean }>("/api/auth/register/", { method: "POST", body: form });
      if (r.email_failed) toast("Your account was created, but we couldn't send the email. Try 'send a new code'.", "error");
      navigate("/accounts/verify", { state: { verify: r.verify } });
    } catch (ex) {
      if (ex instanceof ApiError && Object.keys(ex.fieldErrors).length) {
        setErrors(ex.fieldErrors);
        setErr(ex.fieldErrors.__all__?.[0] ?? null);
      } else setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Steps step={1} />
      <h1>Create your account</h1>
      <p className="auth-lead">For IsDB staff, Regional Hubs and partners working on Bank projects.</p>
      <FormAlert text={err} />
      <form className="form" noValidate onSubmit={submit}>
        <div className="field-row">
          <Field label="First name" autoComplete="given-name" autoFocus value={form.first_name} onChange={set("first_name")} errors={errors.first_name} />
          <Field label="Last name" autoComplete="family-name" value={form.last_name} onChange={set("last_name")} errors={errors.last_name} />
        </div>
        <Field label="Work email" type="email" autoComplete="email" placeholder="name@isdb.org" value={form.email} onChange={set("email")} errors={errors.email} />
        <Field label="Password" type="password" autoComplete="new-password" help="At least 8 characters. Avoid common words and numbers only."
          value={form.password1} onChange={set("password1")} errors={errors.password1} />
        <Field label="Confirm password" type="password" autoComplete="new-password" value={form.password2} onChange={set("password2")} errors={errors.password2} />
        <label className={`check${errors.accept ? " has-error" : ""}`}>
          <input type="checkbox" className="checkbox" checked={form.accept} onChange={set("accept")} />
          <span>I agree to use GEIDA data for IsDB project work</span>
        </label>
        {errors.accept && <p className="field-error"><CircleAlert aria-hidden="true" />Please confirm to continue.</p>}
        <button className="btn btn-dark btn-block" type="submit" disabled={busy}>Create account</button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/accounts/sign-in">Sign in</Link></p>
    </>
  );
}
