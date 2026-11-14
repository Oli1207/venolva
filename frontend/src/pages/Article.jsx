import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { categoryLabel, conditionLabel, fmtPrice } from "../labels";
import { Avatar, BackButton, Empty, Loading, Verified } from "../ui";
import { Photo } from "./Marche";

const REASONS = [["scam", "Arnaque suspectée"], ["forbidden", "Article interdit"], ["wrong", "Annonce trompeuse"], ["other", "Autre"]];

export default function Article() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: l, loading, error, reload } = useFetch(`/listings/${id}/`);
  const { busy, error: actError, run } = useAction();
  const [reporting, setReporting] = useState(false);
  const [reason, setReason] = useState("scam");
  const [reported, setReported] = useState("");

  if (loading) return <main className="page bare"><div className="topbar"><BackButton /></div><Loading /></main>;
  if (error) return <main className="page bare"><div className="topbar"><BackButton /></div><Empty title="Annonce introuvable">Elle a peut-être été vendue ou retirée.</Empty></main>;

  const contact = () => run(async () => { const r = await api.post(`/listings/${l.id}/contact/`); nav(`/messages/${r.conversation}`); });
  const setStatus = (status) => run(async () => { await api.patch(`/listings/${l.id}/`, { status }); await reload(); });
  const remove = () => run(async () => { await api.del(`/listings/${l.id}/`); nav("/mes-annonces", { replace: true }); });
  const report = () => run(async () => { const r = await api.post(`/listings/${l.id}/report/`, { reason }); setReported(r.detail); setReporting(false); });

  const handover = l.handover_at_gym && l.gym_name ? `En main propre à ${l.gym_name}` : "À convenir avec le vendeur";

  return (
    <main className="page bare" style={{ paddingBottom: 130 }}>
      <div style={{ position: "relative" }}>
        <div className="carousel" aria-label="Photos">
          {(l.photos.length ? l.photos : [null]).map((p, i) => <div key={i}><Photo src={p} alt={`${l.title}, photo ${i + 1}`} size={96} /></div>)}
        </div>
        <div style={{ position: "absolute", left: 20, top: 28 }}><div style={{ width: 40, height: 40, borderRadius: "50%", background: "#fff", display: "grid", placeItems: "center" }}><BackButton to="/fil" /></div></div>
        {l.status !== "active" && <span className="gbadge" style={{ left: "auto", right: 20, top: 36 }}>{l.status === "sold" ? "Vendu" : "Retiré"}</span>}
      </div>

      <div className="pad" style={{ paddingTop: 22 }}>
        <div className="h" style={{ fontSize: 34, lineHeight: 1, letterSpacing: "-0.045em" }}>{fmtPrice(l.price)}</div>
        <h1 style={{ margin: "8px 0 0", fontSize: 20, fontWeight: 600, lineHeight: 1.25 }}>{l.title}</h1>
        {l.description && <p style={{ margin: "10px 0 0", fontSize: 15, lineHeight: 1.5, color: "var(--ink-2)", whiteSpace: "pre-wrap" }}>{l.description}</p>}
      </div>

      <div className="pad" style={{ paddingTop: 12 }}>
        <div className="cr"><span className="l">État</span><span className="v">{conditionLabel(l.condition)}</span></div>
        <div className="cr"><span className="l">Catégorie</span><span className="v">{categoryLabel(l.category)}</span></div>
        <div className="cr"><span className="l">Remise</span><span className="v">{handover}</span></div>
      </div>

      <div className="pad" style={{ paddingTop: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 0", borderTop: "1px solid var(--line)" }}>
          <Avatar person={l.seller} size={42} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15, display: "flex", alignItems: "center", gap: 6 }}>{l.seller.display_name}{l.seller.pro_verified && <Verified />}</div>
            <div className="small muted" style={{ marginTop: 1 }}>{l.mine ? "Toi" : "Membre"}{l.seller.commune ? ` · ${l.seller.commune}` : ""}</div>
          </div>
        </div>
        {!l.mine && <p className="hint" style={{ margin: 0 }}>Retrouve le vendeur dans un lieu public, de préférence à la salle. Ne paie qu'en récupérant l'article.</p>}
      </div>

      {!l.mine && (
        <div className="pad" style={{ paddingTop: 14 }}>
          {reported ? <p className="hint">{reported}</p> : reporting ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div className="chips">{REASONS.map(([c, label]) => <button key={c} type="button" className={`chip ${reason === c ? "on" : ""}`} style={{ height: 36, fontSize: 13 }} onClick={() => setReason(c)}>{label}</button>)}</div>
              <div style={{ display: "flex", gap: 10 }}><button type="button" className="btn sm" disabled={busy} onClick={report}>Envoyer le signalement</button><button type="button" className="link" onClick={() => setReporting(false)}>Annuler</button></div>
            </div>
          ) : <button type="button" className="link" onClick={() => setReporting(true)}>Signaler cette annonce</button>}
        </div>
      )}
      {actError && <p className="error pad" role="alert">{actError}</p>}

      <div className="bottombar" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
        {l.mine ? (
          <>
            {l.status === "active" ? (
              <button type="button" className="btn" disabled={busy} onClick={() => setStatus("sold")}>Marquer comme vendu</button>
            ) : (
              <button type="button" className="btn" disabled={busy} onClick={() => setStatus("active")}>Remettre en vente</button>
            )}
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              {l.status === "active" && <button type="button" className="link" disabled={busy} onClick={() => setStatus("hidden")}>Retirer l'annonce</button>}
              <button type="button" className="link" disabled={busy} onClick={remove}>Supprimer</button>
            </div>
          </>
        ) : (
          <button type="button" className="btn" disabled={busy || l.status !== "active"} onClick={contact}>{l.status !== "active" ? "Plus disponible" : busy ? "Envoi…" : "Écrire au vendeur"}</button>
        )}
      </div>
    </main>
  );
}
