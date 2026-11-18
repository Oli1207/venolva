import { useState } from "react";
import { api, downloadFile } from "../api";
import { useAction, useFetch } from "../hooks";
import { PRO_LABELS, fmtDateTime, fmtPrice } from "../labels";
import { Loading } from "../ui";
import { Badge, EmptyRow, METHODS, Page, Pager, usePaged } from "./ui";

const STATUS = { pending: ["À verser", "warn"], paid: ["Versé", "ok"], cancelled: ["Annulé", ""] };

function PayeesTable({ onCreated }) {
  const { data, loading, error, reload } = useFetch("/admin/payees/");
  const { busy, error: actError, run } = useAction();
  if (loading && !data) return <Loading />;
  if (error) return <p className="error">{error.message}</p>;
  const create = (u) => run(async () => { await api.post("/admin/payouts/", { payee: u.id }); await Promise.all([reload(), onCreated()]); });

  return (
    <>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Bénéficiaire</th><th className="num">Disponible</th><th className="num">En attente du délai</th><th className="num">En cours de versement</th><th className="num">Déjà versé</th><th>Compte de réception</th><th /></tr></thead>
          <tbody>
            {data.length === 0 ? <EmptyRow cols={7}>Personne n'a encore encaissé de paiement en ligne.</EmptyRow> : data.map((r) => (
              <tr key={r.user.id}>
                <td><b>{r.user.name}</b><div className="small muted">{PRO_LABELS[r.pro_type] || "Gérant"} · {r.user.email || r.user.phone}</div></td>
                <td className="num"><b>{fmtPrice(r.available)}</b></td>
                <td className="num">{fmtPrice(r.waiting)}</td>
                <td className="num">{fmtPrice(r.in_payout)}</td>
                <td className="num">{fmtPrice(r.paid_out)}{r.refund_pending > 0 && <div className="small" style={{ color: "var(--accent-ink)" }}>{fmtPrice(r.refund_pending)} à rembourser</div>}</td>
                <td>{r.account ? <>{METHODS[r.account.method] || r.account.method}<div className="small muted">{r.account.number} · {r.account.holder_name}</div></> : <Badge tone="warn">Non renseigné</Badge>}</td>
                <td className="num"><button type="button" className="btn sm" disabled={busy || r.available <= 0 || !r.account} onClick={() => create(r.user)} title={!r.account ? "Il doit d'abord indiquer où recevoir son argent." : ""}>Créer le reversement</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {actError && <p className="error" role="alert">{actError}</p>}
    </>
  );
}

function PayoutRow({ po, onChange }) {
  const { busy, error, run } = useAction();
  const [ref, setRef] = useState("");
  const [open, setOpen] = useState(false);
  const details = useFetch(`/admin/payouts/${po.id}/`, { enabled: open });
  const [label, tone] = STATUS[po.status];

  return (
    <>
      <tr>
        <td>n°{po.id}<div className="small muted">{fmtDateTime(po.created_at)}</div></td>
        <td><b>{po.payee.name}</b><div className="small muted">{po.payee.email || po.payee.phone}</div></td>
        <td className="num"><b>{fmtPrice(po.amount)}</b></td>
        <td>{METHODS[po.method] || po.method}<div className="small muted">{po.number} · {po.holder_name}</div></td>
        <td><Badge tone={tone}>{label}</Badge>{po.reference && <div className="small muted">Réf. {po.reference}</div>}{po.paid_at && <div className="small muted">{fmtDateTime(po.paid_at)}</div>}</td>
        <td style={{ minWidth: 230 }}>
          {po.status === "pending" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <input aria-label={`Référence du virement n°${po.id}`} className="input" placeholder="Référence du virement" value={ref} onChange={(e) => setRef(e.target.value)} />
              <div className="adm-actions">
                <button type="button" className="btn sm" disabled={busy || !ref.trim()} onClick={() => run(async () => { await api.post(`/admin/payouts/${po.id}/paid/`, { reference: ref }); await onChange(); })}>Marquer versé</button>
                <button type="button" className="link" disabled={busy} onClick={() => run(async () => { await api.post(`/admin/payouts/${po.id}/cancel/`); await onChange(); })}>Annuler</button>
              </div>
            </div>
          )}
          <button type="button" className="link" style={{ marginTop: 6 }} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Masquer le détail" : "Voir le détail"}</button>
          {error && <p className="error" role="alert">{error}</p>}
        </td>
      </tr>
      {open && (
        <tr><td colSpan={6} style={{ background: "#fafaf8" }}>
          {details.loading ? "Chargement…" : (
            <table className="t" style={{ background: "transparent" }}>
              <thead><tr><th>Paiement</th><th className="num">Encaissé</th><th className="num">Commission</th><th className="num">Versé</th></tr></thead>
              <tbody>{details.data?.payments.map((p) => <tr key={p.reference}><td className="small">{p.reference}</td><td className="num">{fmtPrice(p.amount)}</td><td className="num">{fmtPrice(p.fee)}</td><td className="num">{fmtPrice(p.net)}</td></tr>)}</tbody>
            </table>
          )}
        </td></tr>
      )}
    </>
  );
}

export default function Payouts() {
  const [status, setStatus] = useState("pending");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/payouts/", { status });
  const { error: dlError, run } = useAction();

  return (
    <Page title="Reversements" sub="L'argent encaissé appartient aux pros et aux salles, moins ta commission. Après la séance et le délai d'attente, tu crées un reversement, tu fais le virement (Wave, Orange, MTN…), puis tu notes sa référence.">
      <div className="adm-section" style={{ marginTop: 0 }}>
        <h2>Soldes</h2>
        <PayeesTable onCreated={reload} />
      </div>

      <div className="adm-section">
        <h2>Reversements</h2>
        <div className="adm-form" style={{ marginBottom: 14 }}>
          <div className="field"><label className="k" htmlFor="rs">Statut</label>
            <select id="rs" className="input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value); }}><option value="">Tous</option>{Object.entries(STATUS).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <button type="button" className="btn ghost" onClick={() => run(() => downloadFile("/admin/payouts/export/?status=pending", "reversements-a-verser.csv"))}>Exporter les reversements à verser (CSV)</button>
        </div>
        {dlError && <p className="error" role="alert">{dlError}</p>}
        <div className="tbl-wrap">
          <table className="t">
            <thead><tr><th>Reversement</th><th>Bénéficiaire</th><th className="num">Montant</th><th>Verser sur</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {loading && !data ? <EmptyRow cols={6}>Chargement…</EmptyRow> : error ? <EmptyRow cols={6}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={6}>Aucun reversement.</EmptyRow> : data.results.map((po) => <PayoutRow key={po.id} po={po} onChange={reload} />)}
            </tbody>
          </table>
        </div>
        {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
      </div>
    </Page>
  );
}
