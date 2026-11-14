import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { fmtDateTime, fmtPrice } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

const REASON = { scam: "Arnaque suspectée", forbidden: "Article interdit", wrong: "Annonce trompeuse", other: "Autre" };
const LISTING = { active: ["En vente", "ok"], sold: ["Vendue", ""], hidden: ["Retirée", "bad"] };

function Row({ r, onChange }) {
  const { busy, error, run } = useAction();
  const [label, tone] = LISTING[r.listing.status];
  const act = (action) => run(async () => { await api.post(`/admin/reports/${r.id}/${action}/`); await onChange(); });
  return (
    <tr>
      <td>{fmtDateTime(r.created_at)}</td>
      <td><b>{r.listing.title}</b><div className="small muted">{fmtPrice(r.listing.price)} · vendeur {r.listing.seller.name} ({r.listing.seller.phone})</div><Badge tone={tone}>{label}</Badge></td>
      <td><b>{REASON[r.reason] || r.reason}</b>{r.detail && <div className="small">{r.detail}</div>}<div className="small muted">par {r.reporter.name}{r.reports_on_listing > 1 ? ` · ${r.reports_on_listing} signalements sur cette annonce` : ""}</div></td>
      <td>
        {r.handled ? <Badge>Traité</Badge> : (
          <div className="adm-actions">
            <button type="button" className="btn sm" disabled={busy} onClick={() => act("hide")}>Retirer l'annonce</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("dismiss")}>Ignorer</button>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function Moderation() {
  const [handled, setHandled] = useState("0");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/reports/", { handled });
  return (
    <Page title="Modération" sub="Les annonces signalées par les membres. Retirer une annonce clôt aussi tous ses signalements.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field"><label className="k" htmlFor="hs">Afficher</label>
          <select id="hs" className="input" value={handled} onChange={(e) => { setPage(1); setHandled(e.target.value); }}><option value="0">À traiter</option><option value="1">Traités</option><option value="all">Tous</option></select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Annonce</th><th>Signalement</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={4}>Chargement…</EmptyRow> : error ? <EmptyRow cols={4}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={4}>Rien à modérer.</EmptyRow> : data.results.map((r) => <Row key={r.id} r={r} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
