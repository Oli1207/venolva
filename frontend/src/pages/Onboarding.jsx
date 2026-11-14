import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { COMMUNES, DAY_LETTERS, GOALS, LEVELS, PERIODS } from "../labels";
import { BackButton, Icon, Loading, Radio, Toggle } from "../ui";

const STEPS = 3;

export default function Onboarding() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const { busy, error, run, setError } = useAction();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    goals: user.profile.goals || [],
    level: user.profile.level || "debutant",
    gym: user.profile.gym || null,
    days: user.profile.days || [],
    periods: user.profile.periods || [],
    outdoor: user.profile.outdoor || false,
    display_name: user.display_name || "",
    commune: user.commune || "",
  });
  const [q, setQ] = useState("");
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  // Mises à jour fonctionnelles : des clics rapprochés ne s'écrasent pas.
  const toggleIn = (key, v) =>
    setForm((f) => ({ ...f, [key]: f[key].includes(v) ? f[key].filter((x) => x !== v) : [...f[key], v] }));
  const toggleGoal = (code) => {
    if (!form.goals.includes(code) && form.goals.length >= 2) return setError("Deux objectifs au maximum.");
    setError("");
    toggleIn("goals", code);
  };

  const gymsPath = `/gyms/?${new URLSearchParams({ ...(form.commune ? { commune: form.commune } : {}), ...(q ? { q } : {}) })}`;
  const gyms = useFetch(gymsPath, { enabled: step === 1 });

  const valid = [
    form.goals.length > 0,
    form.commune && form.gym && form.days.length > 0 && form.periods.length > 0,
    form.display_name.trim().length >= 2,
  ][step];

  const finish = () =>
    run(async () => {
      const me = await api.patch("/auth/me/", {
        display_name: form.display_name.trim(),
        commune: form.commune,
        profile: { goals: form.goals, level: form.level, gym: form.gym, days: form.days, periods: form.periods, outdoor: form.outdoor, onboarded: true },
      });
      setUser(me);
      nav("/fil", { replace: true });
    });

  const next = () => (step < STEPS - 1 ? (setError(""), setStep(step + 1)) : finish());

  return (
    <main className="page bare">
      <div className="topbar" style={{ gap: 16 }}>
        {step > 0 ? <button type="button" className="back" aria-label="Étape précédente" onClick={() => setStep(step - 1)}><Icon name="back" /></button> : <span style={{ width: 26 }} />}
        <div className="progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS} aria-valuenow={step + 1}><i style={{ width: `${((step + 1) / STEPS) * 100}%` }} /></div>
        <span className="k">{step + 1} / {STEPS}</span>
      </div>

      <div className="pad" style={{ paddingTop: 32 }}>
        <h1 className="h" style={{ fontSize: 34, lineHeight: 1.02 }}>{["Ton objectif ?", "Où et quand ?", "Qui es-tu ?"][step]}</h1>
        {step === 0 && <p style={{ margin: "10px 0 0", fontSize: 15, lineHeight: 1.5, color: "#55554f" }}>Tu peux en choisir deux. On te propose des binômes qui visent la même chose.</p>}
      </div>

      {step === 0 && (
        <>
          <div className="rows" style={{ paddingTop: 14 }}>
            {GOALS.map((g) => (
              <button type="button" key={g.code} className="row" style={{ minHeight: 62 }} onClick={() => toggleGoal(g.code)} aria-pressed={form.goals.includes(g.code)}>
                <div><div style={{ fontSize: 16, fontWeight: form.goals.includes(g.code) ? 700 : 500 }}>{g.label}</div><div className="small muted">{g.sub}</div></div>
                <Radio on={form.goals.includes(g.code)} />
              </button>
            ))}
          </div>
          <div className="pad" style={{ paddingTop: 20, display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="k">Ton niveau</div>
            <div className="seg">{LEVELS.map((l) => <button type="button" key={l.code} className={form.level === l.code ? "on" : ""} onClick={() => set({ level: l.code })}>{l.label}</button>)}</div>
          </div>
        </>
      )}

      {step === 1 && (
        <div className="pad" style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 18 }}>
          <div className="field">
            <label className="k" htmlFor="commune-gym">Ta commune</label>
            <select id="commune-gym" className="input" value={form.commune} onChange={(e) => set({ commune: e.target.value, gym: null })}>
              <option value="">Choisir</option>
              {COMMUNES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <div className="input" style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--mute)" }}>
              <Icon name="search" size={18} />
              <input aria-label="Chercher une salle" placeholder="Ta salle" value={q} onChange={(e) => setQ(e.target.value)} style={{ border: 0, outline: "none", flex: 1, background: "none", minWidth: 0 }} />
            </div>
            {gyms.loading ? <Loading /> : gyms.data?.length ? (
              <div style={{ marginTop: 6 }}>
                {gyms.data.map((g) => (
                  <button type="button" key={g.id} className="row" style={{ minHeight: 64 }} onClick={() => set({ gym: g.id })} aria-pressed={form.gym === g.id}>
                    <div><div style={{ fontSize: 16, fontWeight: form.gym === g.id ? 700 : 500 }}>{g.name}</div><div className="small muted">{g.commune} · {g.members_count} membre{g.members_count > 1 ? "s" : ""}</div></div>
                    <Radio on={form.gym === g.id} />
                  </button>
                ))}
              </div>
            ) : <p className="hint" style={{ padding: "14px 0" }}>Aucune salle trouvée. Essaie une autre commune.</p>}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div className="k">Ton créneau</div>
            <div className="chips">{PERIODS.map((p) => <button type="button" key={p.code} className={`chip ${form.periods.includes(p.code) ? "on" : ""}`} aria-pressed={form.periods.includes(p.code)} onClick={() => toggleIn("periods", p.code)}>{p.label} · {p.sub}</button>)}</div>
            <div className="days" role="group" aria-label="Jours">{DAY_LETTERS.map((d, i) => <button type="button" key={i} aria-label={["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][i]} aria-pressed={form.days.includes(i)} className={`day ${form.days.includes(i) ? "on" : ""}`} onClick={() => toggleIn("days", i)}>{d}</button>)}</div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 14 }}>
            <span style={{ flex: 1 }}>Ouvert aussi au plein air : stade, plage, parc.</span>
            <Toggle on={form.outdoor} onChange={(v) => set({ outdoor: v })} label="Plein air" />
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="pad" style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="field"><label className="k" htmlFor="name">Prénom et initiale</label><input id="name" className="input" placeholder="Olivier K." value={form.display_name} onChange={(e) => set({ display_name: e.target.value })} maxLength={60} /></div>
          <p className="hint">Les autres membres voient ton prénom, ton initiale, ta commune et ta salle. Jamais ton numéro.</p>
        </div>
      )}

      <div className="pad" style={{ marginTop: "auto", paddingTop: 20, paddingBottom: 30, display: "flex", flexDirection: "column", gap: 10 }}>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn" disabled={!valid || busy} onClick={next}>{step < STEPS - 1 ? "Continuer" : busy ? "Enregistrement…" : "Terminer"}</button>
      </div>
    </main>
  );
}
