import { Link, useNavigate, useParams } from "react-router-dom";
import { useFetch } from "../hooks";
import { PRO_LABELS, fmtPrice, modesLabel } from "../labels";
import { Avatar, BackButton, Empty, Loading, Verified } from "../ui";
import { useStartChat } from "./Binomes";

export default function ProProfil() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: p, loading, error } = useFetch(`/pros/${id}/`);
  const chat = useStartChat();

  if (loading) return <main className="page bare"><div className="topbar"><BackButton /></div><Loading /></main>;
  if (error) return <main className="page bare"><div className="topbar"><BackButton /></div><Empty title="Profil introuvable">{error.message}</Empty></main>;

  const cheapest = p.services.length ? Math.min(...p.services.map((s) => s.price)) : null;

  return (
    <main className="page bare" style={{ paddingBottom: 100 }}>
      <div className="topbar"><BackButton /></div>
      <div className="pad" style={{ paddingTop: 16, display: "flex", alignItems: "center", gap: 16 }}>
        <Avatar person={p.person} size={72} />
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}><span className="h" style={{ fontSize: 26, lineHeight: 1.1 }}>{p.person.display_name}</span><Verified size={16} /></div>
          <div style={{ fontSize: 14, color: "#55554f", marginTop: 4 }}>{p.speciality || PRO_LABELS[p.person.pro_type]}</div>
          <div className="small muted" style={{ marginTop: 2 }}>{p.gym?.name || p.person.commune}</div>
        </div>
      </div>

      <div className="stats" style={{ paddingTop: 20 }}>
        <div className="stat"><div className="sv">{p.sessions_done}</div><div className="sl">Séances données</div></div>
        {p.years_experience != null && <div className="stat"><div className="sv">{p.years_experience} ans</div><div className="sl">D'expérience</div></div>}
        <div className="stat"><div className="sv">{p.weekdays.length}</div><div className="sl">Jours par semaine</div></div>
      </div>

      {p.bio && <p className="pad" style={{ margin: "18px 0 0", fontSize: 15, lineHeight: 1.5, color: "var(--ink-3, #3f3f3b)" }}>{p.bio}</p>}

      <div className="tabs" style={{ marginTop: 18 }}><span className="tab on">Services</span></div>
      <div className="rows">
        {p.services.length === 0 && <p className="hint" style={{ padding: "16px 0" }}>Aucun service pour l'instant.</p>}
        {p.services.map((s) => (
          <button type="button" key={s.id} className="row" style={{ minHeight: 72 }} onClick={() => nav(`/pros/${p.person.id}/reserver?service=${s.id}`)}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 16 }}>{s.name}</div>
              <div className="small muted" style={{ marginTop: 2 }}>{s.duration_min} min · {modesLabel(s.modes)}</div>
              {s.kind === "duo" && <div className="small" style={{ color: "var(--accent-ink)", fontWeight: 600, marginTop: 2 }}>Avec ton binôme</div>}
            </div>
            <span className="price" style={{ fontSize: 16 }}>{fmtPrice(s.price)}</span>
          </button>
        ))}
      </div>
      <div className="pad" style={{ paddingTop: 10 }}>
        <button type="button" className="link" disabled={chat.busy} onClick={() => chat.start(p.person.id)}>Poser une question avant de réserver</button>
      </div>

      {cheapest != null && (
        <div className="bottombar">
          <div><div className="k">À partir de</div><div className="price" style={{ fontSize: 22, marginTop: 2 }}>{fmtPrice(cheapest)}</div></div>
          <Link to={`/pros/${p.person.id}/reserver`} className="btn" style={{ flex: 1 }}>Réserver</Link>
        </div>
      )}
    </main>
  );
}
