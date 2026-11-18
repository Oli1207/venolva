import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { defaultLocalInput, localToIso } from "../labels";
import { Avatar, Icon, Toggle } from "../ui";

export default function Publier() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { busy, error, run } = useAction();
  const [body, setBody] = useState("");
  const [buddy, setBuddy] = useState(false);
  const [article, setArticle] = useState(false);
  const [title, setTitle] = useState("");
  const canArticle = user.is_staff || (user.pro_type && user.pro_verified);
  const [when, setWhen] = useState(defaultLocalInput(18));
  const [gym, setGym] = useState(user.profile.gym || "");
  const gyms = useFetch(`/gyms/?${new URLSearchParams(user.commune ? { commune: user.commune } : {})}`);

  const publish = () =>
    run(async () => {
      const made = await api.post("/posts/", {
        kind: article ? "article" : buddy ? "buddy" : "text",
        title: article ? title.trim() : "",
        body: body.trim(),
        gym: buddy && gym ? Number(gym) : null,
        starts_at: buddy ? localToIso(when) : null,
      });
      nav(article ? `/publication/${made.id}` : "/fil", { replace: true });
    });

  return (
    <main className="page bare">
      <div className="topbar between">
        <button type="button" className="link" style={{ fontSize: 15, textDecoration: "none", color: "var(--ink-2)" }} onClick={() => nav(-1)}>Annuler</button>
        <button type="button" className="btn sm" disabled={busy || (article ? title.trim().length < 5 || body.trim().length < 100 : body.trim().length < 3)} onClick={publish} style={{ height: 40, padding: "0 20px", fontSize: 14 }}>{busy ? "…" : "Publier"}</button>
      </div>

      <div className="pad" style={{ paddingTop: 22, display: "flex", alignItems: "center", gap: 12 }}>
        <Avatar person={user} size={42} />
        <div><div style={{ fontWeight: 600, fontSize: 15 }}>{user.display_name}</div><div className="small muted">{user.commune}</div></div>
      </div>

      <div className="pad" style={{ paddingTop: 18 }}>
        <label htmlFor="body" style={{ position: "absolute", left: -9999 }}>Texte de la publication</label>
        {article && <input className="input" aria-label="Titre de l'article" maxLength={120} placeholder="Titre de l'article" value={title} onChange={(e) => setTitle(e.target.value)} style={{ border: 0, background: "transparent", padding: 0, fontSize: 24, fontWeight: 700, marginBottom: 10 }} />}
        <textarea id="body" className="input" rows={article ? 12 : 4} maxLength={article ? 5000 : 600} placeholder={article ? "Écris ton article (100 caractères au moins)…" : buddy ? "Je cherche quelqu'un pour la salle demain matin…" : "Partage une séance, un conseil…"} value={body} onChange={(e) => setBody(e.target.value)} style={{ border: 0, background: "transparent", padding: 0, fontSize: article ? 17 : 19 }} autoFocus />
        {article && <div className="small muted">{body.trim().length} / 5000</div>}
      </div>

      <div className="rows" style={{ paddingTop: 6 }}>
        {canArticle && (
          <div className="row" style={{ cursor: "default" }}>
            <span style={{ flex: 1, fontWeight: article ? 700 : 500, fontSize: 16 }}>Écrire un article</span>
            <Toggle on={article} onChange={(v) => { setArticle(v); if (v) setBuddy(false); }} label="Écrire un article" />
          </div>
        )}
        {!article && <div className="row" style={{ cursor: "default" }}>
          <span style={{ width: 36, height: 36, borderRadius: 10, background: buddy ? "var(--ink)" : "#e8e8e3", color: buddy ? "#fff" : "var(--ink)", display: "grid", placeItems: "center" }}><Icon name="users" size={18} stroke={1.9} /></span>
          <span style={{ flex: 1, fontWeight: buddy ? 700 : 500, fontSize: 16 }}>Chercher un binôme</span>
          <Toggle on={buddy} onChange={setBuddy} label="Chercher un binôme" />
        </div>}
        {buddy && !article && (
          <div style={{ padding: "8px 0 14px 50px", display: "flex", flexDirection: "column", gap: 12 }}>
            <div className="field"><label className="k" htmlFor="when">Quand</label><input id="when" className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></div>
            <div className="field">
              <label className="k" htmlFor="gym">Où</label>
              <select id="gym" className="input" value={gym} onChange={(e) => setGym(e.target.value)}>
                <option value="">Pas de salle précise</option>
                {(gyms.data || []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      <div className="pad" style={{ marginTop: "auto", paddingBottom: 30 }}>
        {error && <p className="error" role="alert">{error}</p>}
        <div className="hint">Du texte, et un ajout au maximum.</div>
      </div>
    </main>
  );
}
