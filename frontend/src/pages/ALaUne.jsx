import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { fmtDateTime } from "../labels";
import { BackButton, Loading } from "../ui";

const STATUS = { pending: "En attente de validation", approved: "Accordée", rejected: "Refusée", cancelled: "Arrêtée" };

// Demander la mise à la une d'un de ses contenus, et suivre ce que ça rapporte (vues, clics).
export default function ALaUne() {
  const { user } = useAuth();
  const mine = useFetch("/features/mine/");
  const posts = useFetch("/posts/?mine=1");
  const listings = useFetch("/listings/?mine=1");
  const { busy, error, run } = useAction();
  const [pick, setPick] = useState("");
  const [days, setDays] = useState(3);

  const options = [
    ...(user.pro_verified ? [["pro", user.id, "Mon profil pro"]] : []),
    ...(posts.data?.results || []).filter((p) => p.kind === "article").map((p) => ["post", p.id, `Article : ${p.title}`]),
    ...(listings.data?.results || []).filter((l) => l.status === "active").map((l) => ["listing", l.id, `Annonce : ${l.title}`]),
  ];
  const max = mine.data?.max_days || 14;

  const send = (e) => {
    e.preventDefault();
    const [kind, target] = pick.split(":");
    run(async () => { await api.post("/features/", { kind, target, days: Number(days), commune: "" }); setPick(""); await mine.reload(); });
  };

  return (
    <main className="page bare">
      <div className="topbar"><BackButton to="/profil" /></div>
      <div className="pad" style={{ paddingBottom: 30 }}>
        <h1 className="h" style={{ fontSize: 30, margin: "6px 0 6px" }}>À la une</h1>
        <p className="hint" style={{ marginTop: 0 }}>Mets en avant ton profil pro, un article ou une annonce dans le fil de tout le monde. L'équipe valide chaque demande ; les places sont limitées.</p>
        <form onSubmit={send} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="field"><label className="k" htmlFor="what">Quoi mettre en avant</label>
            <select id="what" className="input" value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">Choisir…</option>
              {options.map(([k, id, label]) => <option key={`${k}:${id}`} value={`${k}:${id}`}>{label}</option>)}
            </select>
          </div>
          <div className="field"><label className="k" htmlFor="d">Combien de jours (jusqu'à {max})</label><input id="d" className="input" type="number" min={1} max={max} value={days} onChange={(e) => setDays(e.target.value)} /></div>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn" disabled={busy || !pick}>{busy ? "Envoi…" : "Envoyer la demande"}</button>
          {options.length === 0 && <p className="hint">Rien à mettre en avant pour l'instant : publie un article (compte pro validé) ou une annonce.</p>}
        </form>

        <div className="k" style={{ margin: "26px 0 6px" }}>Mes demandes</div>
        {mine.loading ? <Loading /> : mine.data.results.length === 0 ? <p className="hint">Aucune demande.</p> : mine.data.results.map((f) => (
          <div key={f.id} className="row" style={{ cursor: "default", display: "block", padding: "12px 0" }}>
            <div style={{ fontWeight: 600 }}>{f.title}</div>
            <div className="small muted">{f.live ? "En cours" : STATUS[f.status]}{f.ends_at ? ` · jusqu'au ${fmtDateTime(f.ends_at)}` : ` · ${f.requested_days} j demandés`}</div>
            {f.status === "approved" && <div className="small">{f.views} vue{f.views > 1 ? "s" : ""} · {f.clicks} clic{f.clicks > 1 ? "s" : ""}</div>}
            {f.note && <div className="small muted">{f.note}</div>}
          </div>
        ))}
      </div>
    </main>
  );
}
