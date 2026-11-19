import { useState } from "react";
import { fmtDateTime, fmtPrice } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

const STATUS = { pending: ["En attente", "warn"], confirmed: ["Confirmée", "ok"], declined: ["Refusée", "bad"], cancelled: ["Annulée", "bad"], done: ["Terminée", ""] };
const PAYMENT = { unpaid: ["À payer", "warn"], partial: ["Partiel", "warn"], paid: ["Payée", "ok"] };

export default function Reservations() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [payment, setPayment] = useState("");
  const { data, loading, error, page, setPage, pages } = usePaged("/admin/bookings/", { q, status, payment });
  return (
    <Page title="Réservations" sub="Les réservations de pros, en lecture seule, pour répondre aux questions des membres. Les remboursements se traitent dans Paiements.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}><label className="k" htmlFor="bq">Recherche</label><input id="bq" className="input" placeholder="Nom ou e-mail du pro ou du client" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} /></div>
        <div className="field"><label className="k" htmlFor="bs">État</label>
          <select id="bs" className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}><option value="">Tous</option>{Object.entries(STATUS).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <div className="field"><label className="k" htmlFor="bp">Paiement</label>
          <select id="bp" className="input" value={payment} onChange={(e) => { setPage(1); setPayment(e.target.value); }}><option value="">Tous</option>{Object.entries(PAYMENT).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Séance</th><th>Service</th><th>Pro</th><th>Client</th><th>État</th><th>Paiement</th></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={6}>Chargement…</EmptyRow> : error ? <EmptyRow cols={6}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={6}>Aucune réservation.</EmptyRow> : data.results.map((b) => (
              <tr key={b.id}>
                <td>{fmtDateTime(b.starts_at)}</td>
                <td><b>{b.service}</b><div className="small muted">{fmtPrice(b.price_total)}</div></td>
                <td>{b.pro.name}<div className="small muted">{b.pro.email || b.pro.phone}</div></td>
                <td>{b.client.name}<div className="small muted">{b.client.email || b.client.phone}</div></td>
                <td><Badge tone={STATUS[b.status][1]}>{STATUS[b.status][0]}</Badge></td>
                <td><Badge tone={PAYMENT[b.payment_status][1]}>{PAYMENT[b.payment_status][0]}</Badge><div className="small muted">{b.payment_method}</div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
