import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { categoryLabel, fmtDateTime, fmtPrice } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

const STATUS = { active: ["En vente", "ok"], sold: ["Vendue", ""], hidden: ["Retirée", "bad"] };

function Row({ l, onChange }) {
  const { busy, error, run } = useAction();
  const act = (action) => run(async () => { await api.post(`/admin/listings/${l.id}/${action}/`); await onChange(); });
  const [label, tone] = STATUS[l.status];
  return (
    <tr>
      <td>{fmtDateTime(l.created_at)}</td>
      <td><b>{l.title}</b><div className="small muted">{categoryLabel(l.category)} · {fmtPrice(l.price)} · vendeur {l.seller.name} ({l.seller.email || l.seller.phone})</div></td>
      <td><Badge tone={tone}>{label}</Badge></td>
      <td>
        {l.status === "hidden" ? <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("restore")}>Remettre en vente</button> : <button type="button" className="btn sm" disabled={busy} onClick={() => act("hide")}>Retirer l'annonce</button>}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function Annonces() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/listings/", { q, status });
  return (
    <Page title="Annonces" sub="Toutes les annonces du marché. Retirer une annonce la cache sans la supprimer.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}><label className="k" htmlFor="lq">Recherche</label><input id="lq" className="input" placeholder="Titre, vendeur ou e-mail" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} /></div>
        <div className="field"><label className="k" htmlFor="ls">État</label>
          <select id="ls" className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}><option value="">Toutes</option><option value="active">En vente</option><option value="sold">Vendues</option><option value="hidden">Retirées</option></select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Annonce</th><th>État</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={4}>Chargement…</EmptyRow> : error ? <EmptyRow cols={4}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={4}>Aucune annonce.</EmptyRow> : data.results.map((l) => <Row key={l.id} l={l} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
