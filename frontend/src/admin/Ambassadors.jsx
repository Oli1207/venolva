import { useState } from "react";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { fmtDate, fmtDateTime, fmtPrice } from "../labels";
import { Loading } from "../ui";
import { Badge, EmptyRow, METHODS, Page } from "./ui";

export const CONTRACT_STATE = {
  draft: ["À signer", "warn"], upcoming: ["À venir", ""], active: ["En cours", "ok"], ended: ["Terminé", ""], terminated: ["Résilié", "bad"],
};
const STATEMENT = { pending: ["À verser", "warn"], paid: ["Versé", "ok"], cancelled: ["Annulé", ""] };
const MONTH = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });
const today = () => new Date().toISOString().slice(0, 10);

// Les 12 derniers mois terminés, du plus récent au plus ancien.
function pastMonths() {
  const out = [];
  const d = new Date();
  d.setDate(1);
  for (let i = 0; i < 12; i += 1) {
    d.setMonth(d.getMonth() - 1);
    out.push({ value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, label: MONTH.format(d) });
  }
  return out;
}

function Detail({ id, defaults, onChange }) {
  const { data, loading, error, reload } = useFetch(`/admin/ambassadors/${id}/`);
  const { busy, error: actError, run } = useAction();
  const [start, setStart] = useState(today());
  const [months, setMonths] = useState(defaults.months);
  const [pct, setPct] = useState(defaults.pct);
  const [signDate, setSignDate] = useState({});
  const [refs, setRefs] = useState({});
  const [renew, setRenew] = useState(null);
  const [ending, setEnding] = useState(null);
  const [note, setNote] = useState("");
  const [stContract, setStContract] = useState("");
  const [stMonth, setStMonth] = useState(pastMonths()[0].value);
  const refresh = async () => { await Promise.all([reload(), onChange()]); };
  const act = (fn) => run(async () => { await fn(); await refresh(); });

  if (loading && !data) return <Loading />;
  if (error) return <p className="error">{error.message}</p>;
  const signed = data.contracts.filter((c) => c.signed_at && c.state !== "terminated" || c.state === "terminated" && c.signed_at);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, marginTop: 18 }}>
      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 16 }}>Contrats</h3>
        <div className="tbl-wrap">
          <table className="t">
            <thead><tr><th>Période</th><th className="num">Part</th><th>État</th><th>Signé le</th><th /></tr></thead>
            <tbody>
              {data.contracts.length === 0 ? <EmptyRow cols={5}>Aucun contrat.</EmptyRow> : data.contracts.map((c) => {
                const [label, tone] = CONTRACT_STATE[c.state];
                return (
                  <tr key={c.id}>
                    <td><b>{fmtDate(c.start_date)}</b> → <b>{fmtDate(c.end_date)}</b>{c.terminated_at && <div className="small muted">Résilié le {fmtDate(c.terminated_at)}{c.termination_note ? ` : ${c.termination_note}` : ""}</div>}{c.renewal_of && <div className="small muted">Renouvellement</div>}</td>
                    <td className="num"><b>{c.share_pct} %</b></td>
                    <td><Badge tone={tone}>{label}</Badge>{c.days_left != null && <div className="small muted">{c.days_left} jour{c.days_left > 1 ? "s" : ""} restant{c.days_left > 1 ? "s" : ""}</div>}{c.preview && <div className="small" style={{ marginTop: 4 }}>Acquis, pas encore relevé : <b>{fmtPrice(c.preview.amount)}</b> <span className="muted">sur {fmtPrice(c.preview.fees)} de commissions</span></div>}</td>
                    <td>{c.signed_at ? fmtDate(c.signed_at) : "–"}</td>
                    <td style={{ minWidth: 240 }}>
                      {!c.signed_at && c.state !== "terminated" && (
                        <div className="adm-actions">
                          <input type="date" aria-label="Date de signature" className="input" style={{ width: 150 }} value={signDate[c.id] || today()} onChange={(e) => setSignDate({ ...signDate, [c.id]: e.target.value })} />
                          <button type="button" className="btn sm" disabled={busy} onClick={() => act(() => api.post(`/admin/contracts/${c.id}/sign/`, { signed_at: signDate[c.id] || today() }))}>Marquer signé</button>
                        </div>
                      )}
                      {c.signed_at && c.state !== "terminated" && ending !== c.id && renew !== c.id && (
                        <div className="adm-actions">
                          {!c.renewed && <button type="button" className="btn ghost sm" onClick={() => { setRenew(c.id); setMonths(defaults.months); setPct(c.share_pct); }}>Renouveler</button>}
                          <button type="button" className="link" onClick={() => setEnding(c.id)}>Mettre fin</button>
                        </div>
                      )}
                      {renew === c.id && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          <div className="adm-actions">
                            <input type="number" aria-label="Durée en mois" className="input" style={{ width: 86 }} min="1" max="36" value={months} onChange={(e) => setMonths(Number(e.target.value))} /><span className="small muted">mois à</span>
                            <input type="number" aria-label="Part en pourcentage" className="input" style={{ width: 86 }} min="0" max="100" value={pct} onChange={(e) => setPct(Number(e.target.value))} /><span className="small muted">%</span>
                          </div>
                          <div className="adm-actions">
                            <button type="button" className="btn sm" disabled={busy} onClick={() => act(async () => { await api.post(`/admin/contracts/${c.id}/renew/`, { months, share_pct: pct }); setRenew(null); })}>Préparer le renouvellement</button>
                            <button type="button" className="link" onClick={() => setRenew(null)}>Annuler</button>
                          </div>
                        </div>
                      )}
                      {ending === c.id && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          <input aria-label="Motif de la fin du contrat" className="input" placeholder="Motif (fin d'un commun accord…)" value={note} onChange={(e) => setNote(e.target.value)} />
                          <div className="adm-actions">
                            <button type="button" className="btn sm" disabled={busy} onClick={() => act(async () => { await api.post(`/admin/contracts/${c.id}/terminate/`, { note }); setEnding(null); setNote(""); })}>Confirmer la fin</button>
                            <button type="button" className="link" onClick={() => setEnding(null)}>Annuler</button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <form className="adm-form" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); act(() => api.post(`/admin/ambassadors/${id}/contracts/`, { start_date: start, months, share_pct: pct })); }}>
          <div className="field"><label className="k" htmlFor={`cs${id}`}>Début</label><input id={`cs${id}`} type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} /></div>
          <div className="field" style={{ minWidth: 100 }}><label className="k" htmlFor={`cm${id}`}>Durée (mois)</label><input id={`cm${id}`} type="number" className="input" min="1" max="36" value={months} onChange={(e) => setMonths(Number(e.target.value))} /></div>
          <div className="field" style={{ minWidth: 100 }}><label className="k" htmlFor={`cp${id}`}>Part (%)</label><input id={`cp${id}`} type="number" className="input" min="0" max="100" value={pct} onChange={(e) => setPct(Number(e.target.value))} /></div>
          <button className="btn ghost" disabled={busy}>Nouveau contrat</button>
        </form>
      </div>

      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 16 }}>Relevés mensuels</h3>
        <div className="tbl-wrap">
          <table className="t">
            <thead><tr><th>Mois</th><th className="num">Commissions de Venolva</th><th className="num">Part</th><th className="num">À verser</th><th>État</th><th /></tr></thead>
            <tbody>
              {data.statements.length === 0 ? <EmptyRow cols={6}>Aucun relevé pour l'instant.</EmptyRow> : data.statements.map((s) => {
                const [label, tone] = STATEMENT[s.status];
                return (
                  <tr key={s.id}>
                    <td style={{ textTransform: "capitalize" }}>{MONTH.format(new Date(s.month))}<div className="small muted">{s.payments} paiement{s.payments > 1 ? "s" : ""}</div></td>
                    <td className="num">{fmtPrice(s.fees_total)}</td>
                    <td className="num">{s.share_pct} %</td>
                    <td className="num"><b>{fmtPrice(s.amount)}</b></td>
                    <td><Badge tone={tone}>{label}</Badge>{s.reference && <div className="small muted">Réf. {s.reference}</div>}{s.paid_at && <div className="small muted">{fmtDateTime(s.paid_at)}</div>}</td>
                    <td style={{ minWidth: 230 }}>
                      {s.status === "pending" && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          <input aria-label="Référence du virement" className="input" placeholder="Référence du virement" value={refs[s.id] || ""} onChange={(e) => setRefs({ ...refs, [s.id]: e.target.value })} />
                          <div className="adm-actions">
                            <button type="button" className="btn sm" disabled={busy || !(refs[s.id] || "").trim()} onClick={() => act(() => api.post(`/admin/statements/${s.id}/paid/`, { reference: refs[s.id] }))}>Marquer versé</button>
                            <button type="button" className="link" disabled={busy} onClick={() => act(() => api.post(`/admin/statements/${s.id}/cancel/`))}>Annuler</button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {signed.length > 0 && (
          <form className="adm-form" style={{ marginTop: 12 }} onSubmit={(e) => { e.preventDefault(); act(() => api.post(`/admin/ambassadors/${id}/statements/`, { contract: Number(stContract || signed[0].id), month: stMonth })); }}>
            <div className="field"><label className="k" htmlFor={`sm${id}`}>Mois à clôturer</label><select id={`sm${id}`} className="input" value={stMonth} onChange={(e) => setStMonth(e.target.value)}>{pastMonths().map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}</select></div>
            {signed.length > 1 && <div className="field"><label className="k" htmlFor={`sc${id}`}>Contrat</label><select id={`sc${id}`} className="input" value={stContract || signed[0].id} onChange={(e) => setStContract(e.target.value)}>{signed.map((c) => <option key={c.id} value={c.id}>{fmtDate(c.start_date)} → {fmtDate(c.end_date)}</option>)}</select></div>}
            <button className="btn" disabled={busy}>Générer le relevé</button>
          </form>
        )}
        <p className="hint" style={{ margin: "8px 0 0" }}>Un relevé reprend tout ce qui est acquis et n'a pas encore été compté (séances passées, délai d'attente écoulé, aucun remboursement possible). Il se fige à la génération.</p>
      </div>

      <div className="small">
        <b>Compte de réception :</b>{" "}
        {data.account ? <>{METHODS[data.account.method] || data.account.method} · {data.account.number} · {data.account.holder_name}</> : <Badge tone="warn">Pas encore renseigné par elle</Badge>}
        <span className="muted"> · Déjà versé : {fmtPrice(data.totals.paid)} · À verser : {fmtPrice(data.totals.pending)}</span>
      </div>
      {actError && <p className="error" role="alert">{actError}</p>}
    </div>
  );
}

export default function Ambassadors() {
  const list = useFetch("/admin/ambassadors/");
  const settings = useFetch("/admin/settings/");
  const stats = useFetch("/admin/dashboard/");
  const { busy, error, run } = useAction();
  const [phone, setPhone] = useState("");
  const [open, setOpen] = useState(null);
  const v = settings.data?.values;
  const defaults = { months: v?.ambassador_contract_months ?? 6, pct: v?.ambassador_share_pct ?? 0 };
  const zeroCommission = v && v.commission_booking_pct === 0 && v.commission_class_pct === 0;

  const add = (e) => { e.preventDefault(); run(async () => { await api.post("/admin/ambassadors/", { email: phone }); setPhone(""); await list.reload(); }); };

  return (
    <Page title="Ambassadeurs" sub="Une ambassadrice représente Venolva et touche un pourcentage de ce que la plateforme gagne. Contrat de durée fixe, renouvelable en le signant de nouveau.">
      <div className="confirm" style={{ marginTop: 0, background: "var(--surface)", borderColor: "var(--line)" }}>
        <b>Comment sa part est calculée.</b> {defaults.pct}% des <b>commissions que Venolva perçoit</b> sur les paiements en ligne (réservations et cours), une fois la séance rendue et le délai d'attente passé. Jamais sur l'argent des pros ou des salles, et jamais sur un paiement remboursé. Le taux est proposé par défaut dans les Réglages, et chaque contrat garde le sien.
        {zeroCommission && <p style={{ margin: "10px 0 0", color: "#6b2800" }}><b>Attention : la commission de Venolva est à 0 %.</b> Avec 0 % de commission, une part de commission vaut 0 F. Fixe d'abord la commission dans les Réglages.</p>}
      </div>

      <form className="adm-form" onSubmit={add} style={{ margin: "20px 0 8px" }}>
        <div className="field" style={{ minWidth: 240 }}><label className="k" htmlFor="ap">E-mail de la nouvelle ambassadrice</label><input id="ap" className="input" placeholder="amie@exemple.com" type="email" value={phone} onChange={(e) => setPhone(e.target.value)} /></div>
        <button className="btn" disabled={busy || !phone}>Ajouter</button>
      </form>
      <p className="hint" style={{ margin: "0 0 6px" }}>Elle doit d'abord s'être connectée une fois à l'app avec cet e-mail.</p>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="adm-section" style={{ marginTop: 22 }}>
        {list.loading && !list.data ? <Loading /> : list.error ? <p className="error">{list.error.message}</p> : list.data.length === 0 ? <p className="muted">Aucune ambassadrice pour l'instant.</p> : list.data.map((a) => {
          const c = a.contract;
          const [label, tone] = c ? CONTRACT_STATE[c.state] : ["Pas de contrat", "warn"];
          return (
            <article key={a.id} className="tile" style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                <div><b style={{ fontSize: 18 }}>{a.user.name}</b><div className="small muted">{a.user.email || a.user.phone}</div></div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <Badge tone={tone}>{label}</Badge>
                  {c && <span className="small">{fmtDate(c.start_date)} → {fmtDate(c.end_date)} · <b>{c.share_pct} %</b></span>}
                  {a.ending_soon && <Badge tone="warn">Se termine dans {c.days_left} j</Badge>}
                  <span className="small muted">Versé : {fmtPrice(a.totals.paid)} · À verser : {fmtPrice(a.totals.pending)}</span>
                  <button type="button" className="btn ghost sm" aria-expanded={open === a.id} onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? "Fermer" : "Gérer"}</button>
                </div>
              </div>
              {open === a.id && <Detail id={a.id} defaults={defaults} onChange={async () => { await Promise.all([list.reload(), stats.reload()]); }} />}
            </article>
          );
        })}
      </div>
    </Page>
  );
}
