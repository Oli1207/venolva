import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { fmtDateTime, fmtPrice } from "../labels";
import { Badge, EmptyRow, METHODS, PAYMENT_STATUS, PURPOSE, Page, Pager, usePaged } from "./ui";

function Row({ p, onChange }) {
  const { busy, error, run } = useAction();
  const [ref, setRef] = useState("");
  const [open, setOpen] = useState(false);
  const [label, tone] = PAYMENT_STATUS[p.status] || [p.status, ""];
  const needsRefund = ["refund_due", "duplicate", "review"].includes(p.status);

  return (
    <tr>
      <td>{fmtDateTime(p.created_at)}</td>
      <td><span className="small" style={{ wordBreak: "break-all" }}>{p.reference}</span><div className="small muted">{PURPOSE[p.purpose]}</div></td>
      <td><b>{p.payer.name}</b><div className="small muted">{p.payer.email || p.payer.phone}</div></td>
      <td>{p.payee ? <><b>{p.payee.name}</b><div className="small muted">{p.payee.email || p.payee.phone}</div></> : <span className="muted">–</span>}</td>
      <td className="num"><b>{fmtPrice(p.amount)}</b></td>
      <td className="num">{fmtPrice(p.fee)}<div className="small muted">{p.commission_pct} %</div></td>
      <td className="num">{fmtPrice(p.net)}</td>
      <td>{p.provider === "jeko" ? "Jeko" : "Paystack"}<div className="small muted">{METHODS[p.method] || p.method}</div></td>
      <td><Badge tone={tone}>{label}</Badge>{p.payout && <div className="small muted">Reversement n°{p.payout}</div>}{p.refund_reference && <div className="small muted">Réf. {p.refund_reference}</div>}</td>
      <td style={{ minWidth: 190 }}>
        {needsRefund && !open && (
          <div className="adm-actions">
            <button type="button" className="btn sm" onClick={() => setOpen(true)}>Marquer remboursé</button>
            {p.status === "review" && <button type="button" className="btn ghost sm" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/payments/${p.id}/accept/`); await onChange(); })}>Valider</button>}
          </div>
        )}
        {open && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input aria-label="Référence du remboursement" className="input" placeholder="Référence du remboursement" value={ref} onChange={(e) => setRef(e.target.value)} />
            <div className="adm-actions">
              <button type="button" className="btn sm" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/payments/${p.id}/refund/`, { reference: ref }); setOpen(false); await onChange(); })}>Confirmer</button>
              <button type="button" className="link" onClick={() => setOpen(false)}>Annuler</button>
            </div>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

function Webhooks() {
  const { data, loading, page, setPage, pages } = usePaged("/admin/webhooks/");
  const tone = { processed: "ok", ignored: "", unknown: "warn", rejected: "bad" };
  return (
    <div className="adm-section">
      <h2>Notifications des prestataires</h2>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Prestataire</th><th>Événement</th><th>Référence</th><th>Résultat</th><th>Signature</th></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={6}>Chargement…</EmptyRow> : data?.results.length === 0 ? <EmptyRow cols={6}>Aucune notification reçue pour l'instant.</EmptyRow> : data?.results.map((w) => (
              <tr key={w.id}><td>{fmtDateTime(w.created_at)}</td><td>{w.provider === "jeko" ? "Jeko" : "Paystack"}</td><td>{w.event || "–"}</td><td className="small">{w.reference || "–"}</td><td><Badge tone={tone[w.outcome]}>{w.outcome}</Badge> <span className="small muted">{w.detail}</span></td><td>{w.signature_valid ? <Badge tone="ok">Valide</Badge> : <Badge tone="bad">Invalide</Badge>}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </div>
  );
}

export default function AdminPayments() {
  const [status, setStatus] = useState("");
  const [provider, setProvider] = useState("");
  const [q, setQ] = useState("");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/payments/", { status, provider, q });
  const reset = (fn) => (e) => { setPage(1); fn(e.target.value); };

  return (
    <Page title="Paiements" sub="Tout ce qui est encaissé en ligne. Un remboursement se fait chez le prestataire (Jeko ou Paystack) : ici, tu notes qu'il est fait.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field"><label className="k" htmlFor="ps">Statut</label>
          <select id="ps" className="input" value={status} onChange={reset(setStatus)}><option value="">Tous</option>{Object.entries(PAYMENT_STATUS).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <div className="field"><label className="k" htmlFor="pv">Prestataire</label>
          <select id="pv" className="input" value={provider} onChange={reset(setProvider)}><option value="">Tous</option><option value="jeko">Jeko</option><option value="paystack">Paystack</option></select></div>
        <div className="field" style={{ flex: 1, minWidth: 200 }}><label className="k" htmlFor="pq">Recherche</label><input id="pq" className="input" placeholder="Référence, nom ou numéro" value={q} onChange={reset(setQ)} /></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Référence</th><th>Payeur</th><th>Bénéficiaire</th><th className="num">Montant</th><th className="num">Commission</th><th className="num">Net</th><th>Prestataire</th><th>Statut</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={10}>Chargement…</EmptyRow> : error ? <EmptyRow cols={10}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={10}>Aucun paiement.</EmptyRow> : data.results.map((p) => <Row key={p.id} p={p} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
      <Webhooks />
    </Page>
  );
}
