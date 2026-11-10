import { CircleAlert, Eye, EyeOff } from "lucide-react";
import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  errors?: string[];
  help?: string;
  aside?: ReactNode;
};

export function FieldErrors({ errors }: { errors?: string[] }) {
  return <>{(errors ?? []).map((e) => <p key={e} className="field-error"><CircleAlert aria-hidden="true" />{e}</p>)}</>;
}

/** A labelled input with help text and errors; type="password" gets a show/hide toggle. */
export function Field({ label, errors, help, aside, type = "text", id, ...input }: Props) {
  const auto = useId();
  const fid = id ?? auto;
  const [shown, setShown] = useState(false);
  const invalid = !!errors?.length;
  const el = (
    <input className="input" id={fid} type={type === "password" && shown ? "text" : type} aria-invalid={invalid || undefined} {...input} />
  );
  return (
    <div className={`field${invalid ? " has-error" : ""}`}>
      <div className="field-top">
        <label htmlFor={fid}>{label}</label>
        {aside}
      </div>
      {type === "password" ? (
        <div className="password-wrap">
          {el}
          <button type="button" className="pw-toggle" aria-pressed={shown} aria-label={shown ? "Hide password" : "Show password"} onClick={() => setShown((s) => !s)}>
            <Eye className="when-hidden" aria-hidden="true" /><EyeOff className="when-shown" aria-hidden="true" />
          </button>
        </div>
      ) : el}
      {help && <p className="field-help">{help}</p>}
      <FieldErrors errors={errors} />
    </div>
  );
}

export function FormAlert({ text }: { text?: string | null }) {
  if (!text) return null;
  return <div className="alert alert-error" role="alert"><CircleAlert aria-hidden="true" /><div>{text}</div></div>;
}
