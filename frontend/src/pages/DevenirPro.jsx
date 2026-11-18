import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { PRO_TYPES } from "../labels";
import { BackButton, Loading, Radio } from "../ui";

export default function DevenirPro() {
  const { reload } = useAuth();
  const nav = useNavigate();
  const state = useFetch("/pro/me/");
  const gyms = useFetch("/gyms/");
  const { busy, error, run } = useAction();
  const [editing, setEditing] = useState(false);
  const [f, setF] = useState({ pro_type: "", speciality: "", credential: "", years_experience: "", bio: "", gym: "" });
  const set = (patch) => setF((x) => ({ ...x, ...patch }));

  const send = (e) => {
    e.preventDefault();
    run(async () => {
      await api.post("/pro/apply/", {
        pro_type: f.pro_type, speciality: f.speciality.trim(), credential: f.credential.trim(), bio: f.bio.trim(),
        years_experience: f.years_experience === "" ? null : Number(f.years_experience),
        gym: f.gym || null,
      });
      await reload();
      setEditing(false);
      await state.reload();
    });
  };

  if (state.loading) return <main className="page bare"><div className="topbar"><BackButton /></div><Loading /></main>;
  const s = state.data?.status;
  const showForm = s === "none" || (s === "rejected" && editing) || (s === "pending" && editing);

  return (
    <main className="page bare">
      <div className="topbar"><BackButton to="/profil" /></div>
      <div className="pad" style={{ paddingTop: 26 }}>
        <h1 className="h" style={{ fontSize: 34, lineHeight: 1.02 }}>{showForm ? "Quel est ton métier ?" : "Compte pro"}</h1>
        {showForm && <p style={{ margin: "10px 0 0", fontSize: 15, lineHeight: 1.5, color: "#55554f" }}>Tu gardes ton compte membre. Le compte pro s'ajoute dessus.</p>}
      </div>

      {s === "approved" && (
        <div className="pad" style={{ paddingTop: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="callout" style={{ background: "#d3ecdf", color: "#0b5f38" }}>Ton compte pro est validé. Tu as la coche verte.</div>
          <Link to="/pro" className="btn">Ouvrir mon espace pro</Link>
        </div>
      )}

      {s === "pending" && !editing && (
        <div className="pad" style={{ paddingTop: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="callout">Ton dossier est en cours de vérification. Notre équipe contrôle tes justificatifs sous 48 h. Tu seras prévenu dès que c'est validé.</div>
          <button type="button" className="btn ghost" onClick={() => setEditing(true)}>Modifier mon dossier</button>
        </div>
      )}

      {s === "rejected" && !editing && (
        <div className="pad" style={{ paddingTop: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="callout">Ton dossier n'a pas été validé{state.data.review_note ? ` : ${state.data.review_note}` : "."}</div>
          <button type="button" className="btn" onClick={() => setEditing(true)}>Renvoyer un dossier</button>
        </div>
      )}

      {showForm && (
        <form onSubmit={send} style={{ display: "flex", flexDirection: "column" }}>
          <div className="rows" style={{ paddingTop: 12 }}>
            {PRO_TYPES.map((t) => (
              <button type="button" key={t.code} className="row" style={{ minHeight: 52 }} aria-pressed={f.pro_type === t.code} onClick={() => set({ pro_type: t.code })}>
                <span style={{ fontSize: 16, fontWeight: f.pro_type === t.code ? 700 : 500 }}>{t.label}</span>
                <Radio on={f.pro_type === t.code} />
              </button>
            ))}
          </div>
          <div className="pad" style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field"><label className="k" htmlFor="spec">Spécialité</label><input id="spec" className="input" maxLength={80} placeholder="Préparation physique" value={f.speciality} onChange={(e) => set({ speciality: e.target.value })} /></div>
            <div className="field"><label className="k" htmlFor="cred">Justificatif</label><input id="cred" className="input" maxLength={160} placeholder="Numéro d'ordre, diplôme ou registre" value={f.credential} onChange={(e) => set({ credential: e.target.value })} /><span className="hint">Notre équipe te demandera une copie de ta pièce d'identité et de ton diplôme.</span></div>
            <div style={{ display: "flex", gap: 12 }}>
              <div className="field" style={{ flex: 1 }}><label className="k" htmlFor="yrs">Années d'expérience</label><input id="yrs" className="input" type="number" min="0" max="60" value={f.years_experience} onChange={(e) => set({ years_experience: e.target.value })} /></div>
              <div className="field" style={{ flex: 1.4 }}><label className="k" htmlFor="gym">Salle</label><select id="gym" className="input" value={f.gym} onChange={(e) => set({ gym: e.target.value })}><option value="">Aucune</option>{(gyms.data || []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
            </div>
            <div className="field"><label className="k" htmlFor="bio">Présentation</label><textarea id="bio" className="input" rows={3} maxLength={300} placeholder="Ce que tu proposes, à qui tu t'adresses" value={f.bio} onChange={(e) => set({ bio: e.target.value })} /></div>
            {error && <p className="error" role="alert">{error}</p>}
            <button className="btn" disabled={busy || !f.pro_type || f.credential.trim().length < 3} style={{ marginBottom: 28 }}>{busy ? "Envoi…" : "Envoyer mon dossier"}</button>
          </div>
        </form>
      )}
    </main>
  );
}
