import { FlaskConical, MailCheck } from "lucide-react";
import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError, api } from "@/shared/api/client";
import type { User, VerifyState } from "@/shared/api/types";
import { useAuth } from "@/features/auth/AuthContext";
import { FieldErrors } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { useTitle } from "@/shared/lib/dom";
import { safeNext } from "@/features/auth/pages/SignIn";
import { Steps } from "@/features/auth/pages/Register";

export default function Verify() {
  useTitle("Verify your email");
  const { setUser } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const passed = location.state as { verify?: VerifyState; next?: string } | null;
  const [state, setState] = useState<VerifyState | null>(passed?.verify ?? null);
  const [digits, setDigits] = useState<string[]>(Array(6).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [wait, setWait] = useState(passed?.verify?.resend_wait ?? 0);
  const [busy, setBusy] = useState(false);
  const boxes = useRef<(HTMLInputElement | null)[]>([]);

  // Load (or refresh) the pending verification from the session.
  useEffect(() => {
    api<{ verify: VerifyState }>("/api/auth/verify/")
      .then((r) => { setState(r.verify); setWait(r.verify.resend_wait); })
      .catch(() => {
        toast("Sign in to verify your account.", "info");
        navigate("/accounts/sign-in", { replace: true });
      });
  }, [navigate, toast]);

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  async function submit(code: string) {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const r = await api<{ user: User }>("/api/auth/verify/", { method: "POST", body: { code } });
      setUser(r.user);
      toast("Your email is verified. Welcome to GEIDA.", "success");
      navigate(safeNext(passed?.next ?? null), { replace: true });
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : String(ex));
      setDigits(Array(6).fill(""));
      boxes.current[0]?.focus();
    } finally {
      setBusy(false);
    }
  }

  function fill(from: number, text: string) {
    const incoming = text.replace(/\D/g, "").split("");
    const next = [...digits];
    for (let i = from; i < 6 && incoming.length; i++) next[i] = incoming.shift()!;
    setDigits(next);
    const empty = next.findIndex((d) => !d);
    boxes.current[empty === -1 ? 5 : empty]?.focus();
    if (next.every(Boolean)) void submit(next.join(""));
  }
  function onKey(e: KeyboardEvent<HTMLInputElement>, i: number) {
    if (e.key === "Backspace" && !digits[i] && i > 0) {
      e.preventDefault();
      const next = [...digits]; next[i - 1] = ""; setDigits(next);
      boxes.current[i - 1]?.focus();
    }
    if (e.key === "ArrowLeft" && i > 0) boxes.current[i - 1]?.focus();
    if (e.key === "ArrowRight" && i < 5) boxes.current[i + 1]?.focus();
  }
  function onPaste(e: ClipboardEvent<HTMLInputElement>, i: number) {
    e.preventDefault();
    fill(i, e.clipboardData.getData("text"));
  }

  async function resend() {
    try {
      const r = await api<{ verify: VerifyState }>("/api/auth/verify/resend/", { method: "POST" });
      setState(r.verify); setWait(r.verify.resend_wait); setError(null);
      toast("We've sent a new code.", "success");
    } catch (ex) {
      if (ex instanceof ApiError && ex.data.verify) setWait((ex.data.verify as VerifyState).resend_wait);
      toast(ex instanceof Error ? ex.message : String(ex), "error");
    }
  }

  if (!state) return null;
  return (
    <>
      <Steps step={2} />
      <div className="auth-icon"><MailCheck aria-hidden="true" /></div>
      <h1>Check your email</h1>
      <p className="auth-lead">We sent a 6-digit code to <strong>{state.masked_email}</strong>. It expires in {state.minutes} minutes.</p>
      {state.dev_code && (
        <div className="alert alert-info"><FlaskConical aria-hidden="true" /><div>Development mode: your code is <strong>{state.dev_code}</strong>. It is also printed in the runserver console.</div></div>
      )}
      <form className="form" noValidate onSubmit={(e) => { e.preventDefault(); void submit(digits.join("")); }}>
        <fieldset className={`otp${error ? " has-error" : ""}`}>
          <legend>Verification code</legend>
          <div className="otp-boxes">
            {digits.map((d, i) => (
              <input key={i} ref={(el) => { boxes.current[i] = el; }} className="otp-box" type="text" inputMode="numeric" pattern="[0-9]" maxLength={1}
                autoComplete={i === 0 ? "one-time-code" : "off"} aria-label={`Digit ${i + 1}`} autoFocus={i === 0} value={d}
                onChange={(e) => { const v = e.target.value.replace(/\D/g, ""); if (v) fill(i, v); else { const n = [...digits]; n[i] = ""; setDigits(n); } }}
                onKeyDown={(e) => onKey(e, i)} onPaste={(e) => onPaste(e, i)} />
            ))}
          </div>
          <FieldErrors errors={error ? [error] : []} />
        </fieldset>
        <button className="btn btn-dark btn-block" type="submit" disabled={busy || digits.some((x) => !x)}>Verify email</button>
      </form>
      <div className="resend">
        <span>Didn't get it? Check spam, or</span>
        <button type="button" className="link-btn" disabled={wait > 0} onClick={resend}>send a new code{wait > 0 ? ` in ${wait}s` : ""}</button>
      </div>
      <p className="auth-switch">Wrong email? <Link to="/accounts/register">Start again</Link></p>
    </>
  );
}
