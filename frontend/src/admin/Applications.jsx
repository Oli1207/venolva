import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { PRO_TYPES, fmtDateTime } from "../labels";
import { Loading } from "../ui";
import { Badge, Page, Pager, usePaged } from "./ui";

const TYPE = Object.fromEntries(PRO_TYPES.map((t) => [t.code, t.label]));
const STATUS = { pending: ["En attente", "warn"], approved: ["Validé", "ok"], rejected: ["Refusé", "bad"] };

function Card({ a, onChange }) {
  const { busy, error, run } = useAction();
  const [note, setNote] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [label, tone] = STATUS[a.status];

  return (
    <article className="tile" style={{ gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
        <div><b style={{ fontSize: 17 }}>{a.user.name}</b><div className="small muted">{a.user.email || a.user.phone} · envoyé le {fmtDateTime(a.created_at)}</div></div>
        <Badge tone={tone}>{label}</Badge>
      </div>
      <div className="cr"><span className="l">Métier</span><span className="v">{TYPE[a.pro_type] || a.pro_type}</span></div>
      <div className="cr"><span className="l">Justificatif</span><span className="v">{a.credential}</span></div>
      {a.speciality && <div className="cr"><span className="l">Spécialité</span><span className="v">{a.speciality}</span></div>}
      {a.years_experience != null && <div className="cr"><span className="l">Expérience</span><span className="v">{a.years_experience} ans</span></div>}
      {a.gym && <div className="cr"><span className="l">Salle</span><span className="v">{a.gym}</span></div>}
      {a.bio && <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5, color: "var(--ink-2)" }}>{a.bio}</p>}
      {a.review_note && <p className="small" style={{ margin: 0, color: "var(--accent-ink)" }}>Note : {a.review_note}</p>}
      <p className="hint" style={{ margin: 0 }}>Vérifie la pièce d'identité et le diplôme ou le numéro d'ordre avant de valider : la coche verte engage Djinzin.</p>
      {rejecting ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <input aria-label="Motif du refus" className="input" placeholder="Motif, visible par le candidat" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
          <div className="adm-actions">
            <button type="button" className="btn" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/pro-applications/${a.id}/reject/`, { note }); await onChange(); })}>Confirmer le refus</button>
            <button type="button" className="link" onClick={() => setRejecting(false)}>Annuler</button>
          </div>
        </div>
      ) : (
        <div className="adm-actions">
          {a.status !== "approved" && <button type="button" className="btn" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/pro-applications/${a.id}/approve/`); await onChange(); })}>Valider</button>}
          {a.status !== "rejected" && <button type="button" className="btn ghost" onClick={() => setRejecting(true)}>{a.status === "approved" ? "Retirer la validation" : "Refuser"}</button>}
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </article>
  );
}

export default function Applications() {
  const [status, setStatus] = useState("pending");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/pro-applications/", { status });

  return (
    <Page title="Dossiers pro" sub="Coachs, nutritionnistes, kinés, médecins du sport, salles et boutiques. La validation donne la coche verte et ouvre les services et les réservations.">
      <div className="adm-form" style={{ marginBottom: 16 }}>
        <div className="field"><label className="k" htmlFor="as">Afficher</label>
          <select id="as" className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}><option value="pending">À valider</option><option value="approved">Validés</option><option value="rejected">Refusés</option><option value="all">Tous</option></select></div>
      </div>
      {loading && !data ? <Loading /> : error ? <p className="error">{error.message}</p> : data.results.length === 0 ? <p className="muted">Aucun dossier dans cette catégorie.</p> : (
        <div className="tiles" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))" }}>
          {data.results.map((a) => <Card key={a.id} a={a} onChange={reload} />)}
        </div>
      )}
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
