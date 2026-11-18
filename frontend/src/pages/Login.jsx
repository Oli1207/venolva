import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction } from "../hooks";
import { Wordmark } from "../ui";

const looksLikeEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);

export default function Login() {
  const { login } = useAuth();
  const { busy, error, run, setError } = useAction();
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState("");

  const address = email.trim().toLowerCase();

  const requestCode = (e) => {
    e.preventDefault();
    run(async () => {
      const res = await api.public.post("/auth/otp/request/", { email: address });
      setDevCode(res.dev_code || "");
      setCode("");
      setStep("code");
    });
  };

  const verify = (e) => {
    e.preventDefault();
    run(async () => login(await api.public.post("/auth/otp/verify/", { email: address, code })));
  };

  return (
    <main className="page bare">
      <div className="topbar between">
        <Wordmark />
        <span className="k">Abidjan</span>
      </div>

      <div className="pad" style={{ paddingTop: 44 }}>
        <h1 className="h" style={{ fontSize: 44, lineHeight: 0.98 }}>
          Ta salle.<br />Ton objectif.<br />Ton <span style={{ color: "var(--accent)" }}>binôme.</span>
        </h1>
        <p style={{ margin: "20px 0 0", fontSize: 16, lineHeight: 1.5, color: "#55554f", maxWidth: 320 }}>
          Se mettre au sport est plus facile à deux. Djinzin te présente quelqu'un qui s'entraîne comme toi.
        </p>
      </div>

      <form className="pad" onSubmit={step === "email" ? requestCode : verify} style={{ marginTop: "auto", paddingBottom: 30, paddingTop: 28, display: "flex", flexDirection: "column", gap: 12 }}>
        {step === "email" ? (
          <>
            <label htmlFor="mail" className="k">Ton e-mail</label>
            <input id="mail" className="input" type="email" inputMode="email" autoComplete="email" autoCapitalize="none" placeholder="toi@exemple.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            {error && <p className="error" role="alert">{error}</p>}
            <button className="btn" disabled={busy || !looksLikeEmail(address)}>{busy ? "Envoi…" : "Recevoir mon code"}</button>
            <div className="hint" style={{ textAlign: "center" }}>Un code par e-mail. Pas de mot de passe.</div>
          </>
        ) : (
          <>
            <label htmlFor="code" className="k">Code reçu à {address}</label>
            <input id="code" className="input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="000000" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} style={{ letterSpacing: "0.3em", fontSize: 22, fontFamily: "var(--display)", fontWeight: 700 }} autoFocus />
            {devCode && <div className="hint">Mode test : ton code est <span className="devcode">{devCode}</span></div>}
            {error && <p className="error" role="alert">{error}</p>}
            <button className="btn" disabled={busy || code.length !== 6}>{busy ? "Vérification…" : "Continuer"}</button>
            <button type="button" className="link" onClick={() => { setStep("email"); setError(""); }}>Changer d'adresse</button>
            <div className="hint" style={{ textAlign: "center" }}>Pense à regarder tes courriers indésirables.</div>
          </>
        )}
      </form>
    </main>
  );
}
