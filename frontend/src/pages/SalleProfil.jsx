import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { DAY_FULL, ago, dayParts, fmtPrice, fmtTime, hm } from "../labels";
import { PayButton } from "../Pay";
import { Avatar, BackButton, Empty, Loading, Stars, Verified } from "../ui";
import { GymTile } from "./Salles";

function Plans({ gym, requests, reload }) {
  const { busy, error, run } = useAction();
  const pending = new Set((requests || []).filter((r) => r.status === "pending").map((r) => r.plan.id));
  const ask = (id) => run(async () => { await api.post(`/gym-plans/${id}/request/`); await reload(); });
  if (!gym.plans.length) return <Empty title="Pas encore de formule">La salle n'a pas publié ses tarifs.</Empty>;
  return (
    <>
      <div className="rows">
        {gym.plans.map((p) => (
          <div key={p.id} className="row" style={{ minHeight: 76, cursor: "default" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 16 }}>{p.name}</div>
              {p.description && <div className="small muted" style={{ marginTop: 2 }}>{p.description}</div>}
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="price" style={{ fontSize: 16 }}>{fmtPrice(p.price)}</div>
              {!gym.is_owner && (pending.has(p.id) ? <span className="small tag-ok">Demande envoyée</span> : <button type="button" className="link" style={{ color: "var(--accent-ink)", fontWeight: 700 }} disabled={busy} onClick={() => ask(p.id)}>Demander</button>)}
            </div>
          </div>
        ))}
      </div>
      {error && <p className="error pad" role="alert">{error}</p>}
      {!gym.is_owner && <p className="hint pad" style={{ margin: "10px 0 0" }}>La salle est prévenue par message. Tu paies directement sur place.</p>}
    </>
  );
}

function Classes({ gym, reload }) {
  const { busy, error, run } = useAction();
  const act = (id, action) => run(async () => { await api.post(`/gym-classes/${id}/${action}/`); await reload(); });
  if (!gym.classes.length) return <Empty title="Aucun cours prévu">Les prochains cours collectifs apparaîtront ici.</Empty>;
  return (
    <>
      {gym.classes.map((c) => {
        const { day, weekday } = dayParts(c.starts_at);
        // Un cours payant déjà réservé peut être payé en ligne, sinon il se règle sur place.
        const canPay = !gym.is_owner && c.price > 0 && c.my_seat && !c.my_seat.paid;
        return (
          <div key={c.id} className="se" style={{ alignItems: "flex-start", flexWrap: "wrap" }}>
            <div className="dt"><div className="dd">{day}</div><div className="dw">{weekday}</div></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{fmtTime(c.starts_at)} · {c.name}</div>
              <div className="small muted" style={{ marginTop: 3 }}>
                {c.duration_min} min · {c.price ? fmtPrice(c.price) : "Inclus"} · {c.spots_left > 0 ? `${c.spots_left} place${c.spots_left > 1 ? "s" : ""}` : "Complet"}
                {c.my_seat?.paid && <> · <span className="tag-ok">Payé</span></>}
              </div>
            </div>
            {!gym.is_owner && (c.booked
              ? <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act(c.id, "cancel")}>Annuler</button>
              : <button type="button" className="btn sm" disabled={busy || c.spots_left === 0} onClick={() => act(c.id, "book")}>Réserver</button>)}
            {canPay && <div style={{ flexBasis: "100%", paddingLeft: 60 }}><PayButton purpose="class" target={c.my_seat.id} amount={c.price} /></div>}
          </div>
        );
      })}
      {error && <p className="error pad" role="alert">{error}</p>}
    </>
  );
}

function Reviews({ gym, reload }) {
  const reviews = useFetch(`/gyms/${gym.id}/reviews/`);
  const { busy, error, run } = useAction();
  const [rating, setRating] = useState(gym.my_review?.rating || 0);
  const [comment, setComment] = useState(gym.my_review?.comment || "");
  const send = () => run(async () => { await api.post(`/gyms/${gym.id}/reviews/`, { rating, comment }); await Promise.all([reload(), reviews.reload()]); });

  return (
    <>
      {!gym.is_owner && (
        <div className="pad" style={{ paddingTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="k">{gym.my_review ? "Ton avis" : "Donne ton avis"}</div>
          <Stars value={rating} onChange={setRating} size={28} />
          <textarea aria-label="Commentaire" className="input" rows={2} maxLength={300} placeholder="Ce que tu as aimé, ce qui manque" value={comment} onChange={(e) => setComment(e.target.value)} />
          {error && <p className="error" role="alert">{error}</p>}
          <button type="button" className="btn sm" style={{ alignSelf: "flex-start" }} disabled={busy || !rating} onClick={send}>{gym.my_review ? "Mettre à jour" : "Publier mon avis"}</button>
        </div>
      )}
      {reviews.loading ? <Loading /> : reviews.data?.length === 0 ? <Empty title="Aucun avis">Sois le premier à noter cette salle.</Empty> : (
        <div style={{ paddingTop: 8 }}>
          {(reviews.data || []).map((r) => (
            <div key={r.id} className="entry" style={{ alignItems: "flex-start" }}>
              <Avatar person={r.author} size={38} />
              <div className="body">
                <div className="pn">{r.author.display_name}<span className="pm">· {ago(r.created_at)}</span></div>
                <div style={{ marginTop: 3 }}><Stars value={r.rating} size={14} /></div>
                {r.comment && <p className="tx" style={{ fontSize: 14.5 }}>{r.comment}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export default function SalleProfil() {
  const { id } = useParams();
  const gym = useFetch(`/gyms/${id}/`);
  const reqs = useFetch("/gym-requests/");
  const [tab, setTab] = useState("plans");
  const [week, setWeek] = useState(false);

  if (gym.loading) return <main className="page bare"><div className="topbar"><BackButton /></div><Loading /></main>;
  if (gym.error) return <main className="page bare"><div className="topbar"><BackButton /></div><Empty title="Salle introuvable">{gym.error.message}</Empty></main>;
  const g = gym.data;

  return (
    <main className="page bare" style={{ paddingBottom: 24 }}>
      <div className="topbar"><BackButton /></div>
      <div className="pad" style={{ paddingTop: 16, display: "flex", alignItems: "center", gap: 16 }}>
        <GymTile name={g.name} size={72} />
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}><span className="h" style={{ fontSize: 26, lineHeight: 1.1 }}>{g.name}</span>{g.verified && <Verified size={16} />}</div>
          <div style={{ fontSize: 14, color: "#55554f", marginTop: 4 }}>{g.address || g.commune}</div>
          <div style={{ fontSize: 13, marginTop: 3, display: "flex", alignItems: "center", gap: 6 }}>
            {g.today ? (
              <><span style={{ width: 7, height: 7, borderRadius: "50%", background: g.open_now ? "var(--ok)" : "var(--mute-2)" }} />
                <span style={{ color: g.open_now ? "var(--ok)" : "var(--mute)", fontWeight: 600 }}>{g.open_now ? "Ouvert" : "Fermé"}</span>
                <span className="muted">{g.open_now ? `jusqu'à ${hm(g.today.closes)}` : `ouvre à ${hm(g.today.opens)}`}</span></>
            ) : <span className="muted">Fermé aujourd'hui</span>}
          </div>
        </div>
      </div>

      <div className="stats" style={{ paddingTop: 20 }}>
        <div className="stat"><div className="sv">{g.rating_avg != null ? String(g.rating_avg).replace(".", ",") : "–"}</div><div className="sl">{g.reviews_count} avis</div></div>
        <div className="stat"><div className="sv">{g.members_count}</div><div className="sl">Membres</div></div>
        <div className="stat"><div className="sv">{g.plans.length}</div><div className="sl">Formules</div></div>
      </div>

      <Link to={`/binomes?gym=${g.id}`} className="row" style={{ margin: "18px 24px 0", minHeight: 64, width: "auto", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
        <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontWeight: 600, fontSize: 15 }}>{g.members_count} membre{g.members_count > 1 ? "s" : ""} s'entraîne{g.members_count > 1 ? "nt" : ""} ici</div><div className="small muted" style={{ marginTop: 1 }}>Trouve ton binôme dans cette salle</div></div>
        <span aria-hidden="true">›</span>
      </Link>

      {g.description && <p className="pad" style={{ margin: "14px 0 0", fontSize: 14.5, lineHeight: 1.5, color: "#55554f" }}>{g.description}</p>}
      {g.equipment.length > 0 && <div className="pad" style={{ paddingTop: 10 }}><div className="chips">{g.equipment.map((e) => <span key={e} className="small" style={{ background: "#e8e8e3", borderRadius: 14, padding: "5px 11px", fontWeight: 500 }}>{e}</span>)}</div></div>}

      <div className="pad" style={{ paddingTop: 12 }}>
        <button type="button" className="link" onClick={() => setWeek(!week)} aria-expanded={week}>{week ? "Masquer les horaires" : "Voir les horaires de la semaine"}</button>
        {week && (
          <div style={{ marginTop: 6 }}>
            {DAY_FULL.map((name, wd) => {
              const h = g.hours.find((x) => x.weekday === wd);
              return <div key={wd} className="cr" style={{ minHeight: 36 }}><span className="l" style={{ textTransform: "capitalize" }}>{name}</span><span className="v" style={{ fontWeight: h ? 600 : 400 }}>{h ? `${hm(h.opens)} – ${hm(h.closes)}` : "Fermé"}</span></div>;
            })}
          </div>
        )}
      </div>

      {g.is_owner && <div className="pad" style={{ paddingTop: 14 }}><Link to="/ma-salle" className="btn ghost sm" style={{ width: "100%" }}>Gérer ma salle</Link></div>}

      <div className="tabs" style={{ marginTop: 16 }} role="tablist">
        {[["plans", "Abonnements"], ["classes", "Cours"], ["reviews", "Avis"]].map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{label}</button>)}
      </div>
      {tab === "plans" && <Plans gym={g} requests={reqs.data} reload={async () => { await Promise.all([gym.reload(), reqs.reload()]); }} />}
      {tab === "classes" && <Classes gym={g} reload={gym.reload} />}
      {tab === "reviews" && <Reviews gym={g} reload={gym.reload} />}
    </main>
  );
}
