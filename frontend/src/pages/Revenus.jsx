import { useState } from "react";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { fmtDateTime, fmtPrice } from "../labels";
import { BackButton, Empty, Loading } from "../ui";

const METHODS = [["wave", "Wave"], ["orange", "Orange Money"], ["mtn", "MTN MoMo"], ["moov", "Moov Money"]];
const STATUS = { paid: "Encaissé", refund_due: "À rembourser", refunded: "Remboursé" };
const PAYOUT = { pending: "En préparation", paid: "Versé", cancelled: "Annulé" };

export function AccountForm({ account, onSaved }) {
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ method: account?.method || "", number: account?.number?.replace("+225", "") || "", holder_name: account?.holder_name || "" });
  const [saved, setSaved] = useState(false);
  const set = (p) => { setSaved(false); setF((x) => ({ ...x, ...p })); };
  const submit = (e) => { e.preventDefault(); run(async () => { await api.put("/my/payout-account/", f); setSaved(true); await onSaved(); }); };

  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="field"><span className="k">Recevoir sur</span>
        <div className="chips">{METHODS.map(([code, label]) => <button type="button" key={code} aria-pressed={f.method === code} className={`chip ${f.method === code ? "on" : ""}`} onClick={() => set({ method: code })}>{label}</button>)}</div></div>
      <div className="field"><label className="k" htmlFor="rn">Numéro</label>
        <div style={{ display: "flex", gap: 8 }}><div className="prefix">+225</div><input id="rn" className="input" type="tel" inputMode="numeric" placeholder="07 00 00 00 00" value={f.number} onChange={(e) => set({ number: e.target.value })} /></div></div>
      <div className="field"><label className="k" htmlFor="rh">Nom du titulaire</label><input id="rh" className="input" maxLength={80} placeholder="Comme sur le compte" value={f.holder_name} onChange={(e) => set({ holder_name: e.target.value })} /></div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn" disabled={busy || !f.method || f.number.replace(/\D/g, "").length < 10 || f.holder_name.trim().length < 2}>{busy ? "Enregistrement…" : saved ? "Enregistré" : account ? "Mettre à jour" : "Enregistrer"}</button>
    </form>
  );
}

export default function Revenus() {
  const { data, loading, error, reload } = useFetch("/my/earnings/");
  if (loading && !data) return <main className="page bare"><div className="topbar"><BackButton to="/profil" /></div><Loading /></main>;
  if (error) return <main className="page bare"><div className="topbar"><BackButton to="/profil" /></div><Empty title="Impossible de charger tes revenus">{error.message}</Empty></main>;
  const { balance: b, account } = data;
  const needsAccount = !account && (b.available > 0 || b.waiting > 0);

  return (
    <main className="page bare" style={{ paddingBottom: 40 }}>
      <div className="topbar" style={{ paddingBottom: 12 }}><BackButton to="/profil" /><h1 className="h" style={{ fontSize: 28, lineHeight: 1 }}>Mes revenus</h1></div>

      <div className="pad" style={{ paddingTop: 12 }}>
        <div className="k">Disponible</div>
        <div className="h" style={{ fontSize: 46, letterSpacing: "-0.05em", lineHeight: 1.05, marginTop: 4 }}>{fmtPrice(b.available)}</div>
        <p className="small muted" style={{ margin: "8px 0 0", lineHeight: 1.5 }}>
          Après chaque séance, l'argent reste {data.hold_days} jour{data.hold_days > 1 ? "s" : ""} en attente, puis il est versé par l'équipe Venolva dès que ton solde disponible atteint {fmtPrice(data.min_payout)}.
        </p>
      </div>

      <div className="stats" style={{ paddingTop: 20 }}>
        <div className="stat"><div className="sv" style={{ fontSize: 19 }}>{fmtPrice(b.waiting)}</div><div className="sl">En attente</div></div>
        <div className="stat"><div className="sv" style={{ fontSize: 19 }}>{fmtPrice(b.in_payout)}</div><div className="sl">En préparation</div></div>
        <div className="stat"><div className="sv" style={{ fontSize: 19 }}>{fmtPrice(b.paid_out)}</div><div className="sl">Déjà versé</div></div>
      </div>
      {b.refund_pending > 0 && <p className="hint pad" style={{ margin: "10px 0 0", color: "var(--accent-ink)" }}>{fmtPrice(b.refund_pending)} sont remboursés à des clients (annulations) et ne seront pas versés.</p>}

      <div className="pad" style={{ paddingTop: 24 }}>
        {needsAccount && <div className="callout" style={{ marginBottom: 14 }}>Indique où recevoir ton argent : sans cela, l'équipe ne peut pas te verser ce que tu as gagné.</div>}
        <div className="k" style={{ marginBottom: 10 }}>Compte de réception</div>
        <AccountForm account={account} onSaved={reload} />
      </div>

      <div className="adm-section" style={{ marginTop: 26 }}>
        <div className="k pad" style={{ marginBottom: 4 }}>Paiements reçus</div>
        {data.payments.length === 0 ? <p className="hint pad">Aucun paiement en ligne pour l'instant.</p> : data.payments.map((p) => (
          <div key={p.reference} className="entry" style={{ alignItems: "center", padding: "14px 24px" }}>
            <div className="body">
              <div style={{ fontWeight: 600, fontSize: 15 }}>{fmtPrice(p.net)} <span className="small muted" style={{ fontWeight: 400 }}>sur {fmtPrice(p.amount)}</span></div>
              <div className="small muted" style={{ marginTop: 2 }}>
                {p.purpose === "class" ? "Cours" : "Réservation"} · commission {p.commission_pct} % ({fmtPrice(p.fee)}) · {fmtDateTime(p.paid_at)}
              </div>
              <div className="small" style={{ marginTop: 2, color: p.status === "paid" ? "var(--ok)" : "var(--accent-ink)", fontWeight: 600 }}>
                {p.status === "paid" ? (p.in_payout ? "Inclus dans un reversement" : p.available_at && new Date(p.available_at) > new Date() ? `Disponible le ${fmtDateTime(p.available_at).slice(0, 10)}` : "Disponible") : STATUS[p.status]}
              </div>
            </div>
          </div>
        ))}
      </div>

      {data.payouts.length > 0 && (
        <div style={{ marginTop: 22 }}>
          <div className="k pad" style={{ marginBottom: 4 }}>Reversements</div>
          <div className="rows">
            {data.payouts.map((o) => (
              <div key={o.id} className="row" style={{ cursor: "default", minHeight: 58 }}>
                <div style={{ flex: 1 }}><div style={{ fontWeight: 600 }}>{fmtPrice(o.amount)}</div><div className="small muted">{o.paid_at ? fmtDateTime(o.paid_at) : fmtDateTime(o.created_at)}{o.reference ? ` · réf. ${o.reference}` : ""}</div></div>
                <span className="small" style={{ fontWeight: 600, color: o.status === "paid" ? "var(--ok)" : "var(--mute)" }}>{PAYOUT[o.status]}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
