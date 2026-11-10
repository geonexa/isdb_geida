import { Check, KeyRound, Link2Off, LockKeyhole, Send } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError, api } from "@/shared/api/client";
import { Field, FormAlert } from "@/shared/components/Field";
import { useTitle } from "@/shared/lib/dom";

export function ResetRequest() {
  useTitle("Reset password");
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null); setErrors([]);
    try {
      await api("/api/auth/password-reset/", { method: "POST", body: { email } });
      navigate("/accounts/password-reset/sent");
    } catch (ex) {
      if (ex instanceof ApiError && ex.fieldErrors.email) setErrors(ex.fieldErrors.email);
      else setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="auth-icon"><KeyRound aria-hidden="true" /></div>
      <h1>Reset your password</h1>
      <p className="auth-lead">Enter the email you registered with. We'll send you a link to choose a new password.</p>
      <FormAlert text={err} />
      <form className="form" noValidate onSubmit={submit}>
        <Field label="Work email" type="email" autoComplete="email" autoFocus placeholder="name@isdb.org" value={email} onChange={(e) => setEmail(e.target.value)} errors={errors} />
        <button className="btn btn-dark btn-block" type="submit" disabled={busy}>Send reset link</button>
      </form>
      <p className="auth-switch">Remembered it? <Link to="/accounts/sign-in">Back to sign in</Link></p>
    </>
  );
}

export function ResetSent() {
  useTitle("Check your email");
  return (
    <>
      <div className="auth-icon"><Send aria-hidden="true" /></div>
      <h1>Check your email</h1>
      <p className="auth-lead">If an account exists for that address, we've sent a link to reset your password. The link works for 24 hours.</p>
      <ul className="tips">
        <li>Look in your spam or junk folder.</li>
        <li>Make sure you used the email you registered with.</li>
      </ul>
      <Link className="btn btn-outline btn-block" to="/accounts/sign-in">Back to sign in</Link>
      <p className="auth-switch">No email after a few minutes? <Link to="/accounts/password-reset">Try again</Link></p>
    </>
  );
}

export function ResetConfirm() {
  useTitle("Choose a new password");
  const { uid, token } = useParams();
  const navigate = useNavigate();
  const url = `/api/auth/password-reset/${uid}/${token}/`;
  const [valid, setValid] = useState<boolean | null>(null);
  const [form, setForm] = useState({ new_password1: "", new_password2: "" });
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api<{ valid: boolean }>(url).then((r) => setValid(r.valid)).catch(() => setValid(false)); }, [url]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null); setErrors({});
    try {
      await api(url, { method: "POST", body: form });
      navigate("/accounts/password-reset/complete", { replace: true });
    } catch (ex) {
      if (ex instanceof ApiError && ex.data.valid === false) setValid(false);
      else if (ex instanceof ApiError && Object.keys(ex.fieldErrors).length) setErrors(ex.fieldErrors);
      else setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  if (valid === null) return null;
  if (!valid) {
    return (
      <>
        <div className="auth-icon is-warn"><Link2Off aria-hidden="true" /></div>
        <h1>This link no longer works</h1>
        <p className="auth-lead">Reset links expire after 24 hours and can be used once. Ask for a new one to continue.</p>
        <Link className="btn btn-dark btn-block" to="/accounts/password-reset">Send a new link</Link>
      </>
    );
  }
  return (
    <>
      <div className="auth-icon"><LockKeyhole aria-hidden="true" /></div>
      <h1>Choose a new password</h1>
      <p className="auth-lead">Pick a password you don't use anywhere else.</p>
      <FormAlert text={err} />
      <form className="form" noValidate onSubmit={submit}>
        <Field label="New password" type="password" autoComplete="new-password" autoFocus help="At least 8 characters. Avoid common words and numbers only."
          value={form.new_password1} onChange={(e) => setForm({ ...form, new_password1: e.target.value })} errors={errors.new_password1} />
        <Field label="Confirm new password" type="password" autoComplete="new-password"
          value={form.new_password2} onChange={(e) => setForm({ ...form, new_password2: e.target.value })} errors={errors.new_password2} />
        <button className="btn btn-dark btn-block" type="submit" disabled={busy}>Save new password</button>
      </form>
    </>
  );
}

export function ResetComplete() {
  useTitle("Password saved");
  return (
    <>
      <div className="auth-icon is-good"><Check aria-hidden="true" /></div>
      <h1>Password saved</h1>
      <p className="auth-lead">Your new password is ready. Sign in to continue.</p>
      <Link className="btn btn-dark btn-block" to="/accounts/sign-in">Sign in</Link>
    </>
  );
}
