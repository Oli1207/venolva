import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction } from "../hooks";
import { COMMUNES, GOALS, LEVELS } from "../labels";
import { BackButton } from "../ui";

export default function EditerProfil() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const { busy, error, run } = useAction();
  const p = user.profile;
  const [name, setName] = useState(user.display_name || "");
  const [commune, setCommune] = useState(user.commune || "");
  const [bio, setBio] = useState(p.bio || "");
  const [goals, setGoals] = useState(p.goals || []);
  const [level, setLevel] = useState(p.level);

  const toggleGoal = (code) => setGoals((g) => (g.includes(code) ? g.filter((x) => x !== code) : g.length < 2 ? [...g, code] : g));
  const save = (e) => {
    e.preventDefault();
    run(async () => {
      setUser(await api.patch("/auth/me/", { display_name: name.trim(), commune, profile: { bio: bio.trim(), goals, level } }));
      nav("/profil", { replace: true });
    });
  };

  return (
    <main className="page bare">
      <div className="topbar"><BackButton to="/profil" /></div>
      <form className="pad" onSubmit={save} style={{ display: "flex", flexDirection: "column", gap: 16, paddingBottom: 30 }}>
        <h1 className="h" style={{ fontSize: 30, margin: "6px 0 0" }}>Modifier mon profil</h1>
        <div className="field"><label className="k" htmlFor="n">Prénom et initiale</label><input id="n" className="input" maxLength={60} value={name} onChange={(e) => setName(e.target.value)} required /></div>
        <div className="field"><label className="k" htmlFor="c">Commune</label>
          <select id="c" className="input" value={commune} onChange={(e) => setCommune(e.target.value)}>
            <option value="">Choisir</option>
            {COMMUNES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field"><label className="k" htmlFor="b">À propos de moi</label><textarea id="b" className="input" rows={3} maxLength={240} value={bio} onChange={(e) => setBio(e.target.value)} /></div>
        <div className="field"><div className="k">Mes objectifs (2 au maximum)</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, paddingTop: 6 }}>
            {GOALS.map((g) => <button type="button" key={g.code} className={`chip ${goals.includes(g.code) ? "on" : ""}`} aria-pressed={goals.includes(g.code)} onClick={() => toggleGoal(g.code)}>{g.label}</button>)}
          </div>
        </div>
        <div className="field"><div className="k">Mon niveau</div>
          <div className="seg">{LEVELS.map((l) => <button type="button" key={l.code} className={level === l.code ? "on" : ""} onClick={() => setLevel(l.code)}>{l.label}</button>)}</div>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn" disabled={busy || !name.trim() || goals.length === 0}>{busy ? "Enregistrement…" : "Enregistrer"}</button>
      </form>
    </main>
  );
}
