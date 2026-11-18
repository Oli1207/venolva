import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { fmtDateTime } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

const KIND = { post: "Publication", pro: "Pro", gym: "Salle", listing: "Annonce" };
const STATUS = { pending: ["À traiter", "warn"], approved: ["Accordée", "ok"], rejected: ["Refusée", "bad"], cancelled: ["Arrêtée", ""] };

function Row({ f, onChange }) {
  const { busy, error, run } = useAction();
  const [days, setDays] = useState(f.requested_days);
  const act = (action, body) => run(async () => { await api.post(`/admin/features/${f.id}/${action}/`, body); await onChange(); });
  const [label, tone] = STATUS[f.status];
  return (
    <tr>
      <td>{KIND[f.kind]}</td>
      <td><b>{f.title}</b><div className="small muted">par {f.requested_by?.name || "l'équipe"}{f.scope_commune ? ` · ${f.scope_commune}` : ""}{f.sponsored ? " · sponsorisé" : ""}</div></td>
      <td><Badge tone={tone}>{f.live ? "En cours" : label}</Badge>{f.ends_at && <div className="small muted">jusqu'au {fmtDateTime(f.ends_at)}</div>}</td>
      <td>{f.status === "approved" ? `${f.views} vues · ${f.clicks} clics` : `${f.requested_days} j demandés`}</td>
      <td>
        {f.status === "pending" && (
          <div className="adm-actions">
            <input className="input" type="number" min={1} value={days} onChange={(e) => setDays(Number(e.target.value))} style={{ width: 70 }} aria-label="Durée en jours" />
            <button type="button" className="btn sm" disabled={busy} onClick={() => act("approve", { days })}>Accorder</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("reject", { note: window.prompt("Motif du refus (facultatif)") || "" })}>Refuser</button>
          </div>
        )}
        {f.live && <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("end")}>Arrêter</button>}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function Promo() {
  const [status, setStatus] = useState("pending");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/features/", { status });
  return (
    <Page title="À la une" sub="Les demandes de mise en avant. Les places en même temps et la durée maximale se règlent dans Réglages.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field"><label className="k" htmlFor="st">Afficher</label>
          <select id="st" className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}>
            <option value="pending">À traiter</option><option value="approved">Accordées</option><option value="rejected">Refusées</option><option value="all">Toutes</option>
          </select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Type</th><th>Contenu</th><th>État</th><th>Résultats</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={5}>Chargement…</EmptyRow> : error ? <EmptyRow cols={5}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={5}>Aucune demande.</EmptyRow> : data.results.map((f) => <Row key={f.id} f={f} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
