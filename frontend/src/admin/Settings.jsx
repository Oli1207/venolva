import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { fmtDateTime } from "../labels";
import { Loading } from "../ui";
import { EmptyRow, Page } from "./ui";

const PURPOSES = { all: "Tous les paiements", booking: "Réservations de pros", class: "Cours collectifs" };

function show(meta, v) {
  if (meta.type === "choice") return meta.choices.find((c) => c.value === v)?.label || v;
  return `${v}${meta.unit ? ` ${meta.unit}` : ""}`;
}

function Overrides() {
  const { data, loading, error, reload } = useFetch("/admin/commissions/");
  const { busy, error: formError, run } = useAction();
  const [f, setF] = useState({ phone: "", purpose: "all", pct: "", note: "" });

  const add = (e) => {
    e.preventDefault();
    run(async () => {
      await api.post("/admin/commissions/", { phone: f.phone, purpose: f.purpose, pct: Number(f.pct), note: f.note });
      setF({ phone: "", purpose: "all", pct: "", note: "" });
      await reload();
    });
  };

  return (
    <div className="adm-section">
      <h2>Commissions particulières</h2>
      <p className="adm-sub" style={{ marginBottom: 14 }}>Un taux propre à un pro ou à une salle (partenariat, offre de lancement) remplace le taux par défaut. Il s'applique aux prochains paiements ; les paiements déjà encaissés gardent leur taux.</p>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Vendeur</th><th>Concerne</th><th className="num">Taux</th><th>Note</th><th>Depuis</th><th /></tr></thead>
          <tbody>
            {loading ? <EmptyRow cols={6}>Chargement…</EmptyRow> : error ? <EmptyRow cols={6}>{error.message}</EmptyRow> : data.length === 0 ? <EmptyRow cols={6}>Aucune commission particulière.</EmptyRow> : data.map((o) => (
              <tr key={o.id}>
                <td><b>{o.user.name}</b><div className="small muted">{o.user.phone}</div></td>
                <td>{PURPOSES[o.purpose]}</td>
                <td className="num"><b>{o.pct} %</b></td>
                <td>{o.note}</td>
                <td>{fmtDateTime(o.created_at)}</td>
                <td className="num"><button type="button" className="link" onClick={() => run(async () => { await api.del(`/admin/commissions/${o.id}/`); await reload(); })}>Supprimer</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <form className="adm-form" onSubmit={add} style={{ marginTop: 16 }}>
        <div className="field"><label className="k" htmlFor="cp">Numéro du vendeur</label><input id="cp" className="input" placeholder="07 00 00 00 00" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></div>
        <div className="field"><label className="k" htmlFor="cu">Concerne</label><select id="cu" className="input" value={f.purpose} onChange={(e) => setF({ ...f, purpose: e.target.value })}>{Object.entries(PURPOSES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
        <div className="field" style={{ minWidth: 100 }}><label className="k" htmlFor="cr">Taux (%)</label><input id="cr" className="input" type="number" min="0" max="50" value={f.pct} onChange={(e) => setF({ ...f, pct: e.target.value })} /></div>
        <div className="field" style={{ flex: 1 }}><label className="k" htmlFor="cn">Note</label><input id="cn" className="input" maxLength={120} placeholder="Partenaire fondateur" value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></div>
        <button className="btn" disabled={busy || !f.phone || f.pct === ""}>Ajouter</button>
      </form>
      {formError && <p className="error" role="alert">{formError}</p>}
    </div>
  );
}

export default function Settings() {
  const { data, loading, error, reload } = useFetch("/admin/settings/");
  const { busy, error: saveError, run, setError } = useAction();
  const [draft, setDraft] = useState({});
  const [fieldErrors, setFieldErrors] = useState({});
  const [confirming, setConfirming] = useState(false);
  const [saved, setSaved] = useState(false);

  if (loading && !data) return <Loading />;
  if (error) return <p className="error">{error.message}</p>;

  const values = data.values;
  const changes = data.schema.filter((m) => m.key in draft && draft[m.key] !== values[m.key]);
  const current = (m) => (m.key in draft ? draft[m.key] : values[m.key]);
  const set = (m, v) => { setSaved(false); setConfirming(false); setFieldErrors({}); setDraft((d) => ({ ...d, [m.key]: v })); };

  const save = () =>
    run(async () => {
      try {
        await api.patch("/admin/settings/", { values: Object.fromEntries(changes.map((m) => [m.key, draft[m.key]])) });
      } catch (e) {
        if (e.data?.errors) { setFieldErrors(e.data.errors); setConfirming(false); setError("Certains réglages sont invalides."); return; }
        throw e;
      }
      setDraft({});
      setConfirming(false);
      setSaved(true);
      await reload();
    });

  return (
    <Page title="Réglages" sub="Tout ce qui se règle sans toucher au code. Chaque modification est confirmée, datée et inscrite au journal avec son auteur.">
      {data.groups.map((g) => (
        <div key={g.key} className="adm-section" style={{ marginTop: g.key === "finance" ? 0 : undefined }}>
          <h2>{g.label}</h2>
          <div className="tbl-wrap" style={{ padding: "0 20px" }}>
            {data.schema.filter((m) => m.group === g.key).map((m) => {
              const changed = m.key in draft && draft[m.key] !== values[m.key];
              return (
                <div className="setrow" key={m.key}>
                  <div>
                    <label className="lbl" htmlFor={`s-${m.key}`}>{m.label}{changed && <span className="badge warn" style={{ marginLeft: 8 }}>Modifié</span>}</label>
                    {m.help && <div className="hlp">{m.help}</div>}
                    {fieldErrors[m.key] && <p className="error" role="alert" style={{ marginTop: 6 }}>{fieldErrors[m.key]}</p>}
                  </div>
                  {m.type === "choice" ? (
                    <select id={`s-${m.key}`} className="input" value={current(m)} onChange={(e) => set(m, e.target.value)}>{m.choices.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select>
                  ) : (
                    <div className="unitbox">
                      <input id={`s-${m.key}`} className="input" type="number" min={m.min} max={m.max} value={current(m)} onChange={(e) => set(m, e.target.value === "" ? "" : Number(e.target.value))} aria-describedby={`u-${m.key}`} />
                      <span className="u" id={`u-${m.key}`}>{m.unit}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 22, display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        {!confirming ? (
          <button type="button" className="btn" disabled={changes.length === 0} onClick={() => setConfirming(true)}>{changes.length ? `Enregistrer ${changes.length} modification${changes.length > 1 ? "s" : ""}` : "Aucune modification"}</button>
        ) : null}
        {changes.length > 0 && !confirming && <button type="button" className="link" onClick={() => { setDraft({}); setFieldErrors({}); }}>Tout annuler</button>}
        {saved && <span className="badge ok">Réglages enregistrés</span>}
        <span className="small muted" style={{ marginLeft: "auto" }}>
          Dernière modification : {data.updated_by ? `${data.updated_by.name}, ` : ""}{fmtDateTime(data.updated_at)} · <Link to="/admin/journal" style={{ textDecoration: "underline" }}>Historique</Link>
        </span>
      </div>

      {confirming && (
        <div className="confirm" role="alertdialog" aria-label="Confirmer les modifications">
          <b>Tu vas modifier :</b>
          <ul style={{ margin: "10px 0 14px", paddingLeft: 20, lineHeight: 1.7 }}>
            {changes.map((m) => <li key={m.key}>{m.label} : <s>{show(m, values[m.key])}</s> → <b>{show(m, draft[m.key])}</b></li>)}
          </ul>
          <p className="small" style={{ margin: "0 0 12px", color: "#6b2800" }}>Les nouveaux réglages s'appliquent tout de suite aux prochaines actions. Les paiements déjà encaissés ne sont pas modifiés.</p>
          <div className="adm-actions">
            <button type="button" className="btn" disabled={busy} onClick={save}>{busy ? "Enregistrement…" : "Confirmer"}</button>
            <button type="button" className="btn ghost" onClick={() => setConfirming(false)}>Revenir</button>
          </div>
        </div>
      )}
      {saveError && <p className="error" role="alert" style={{ marginTop: 12 }}>{saveError}</p>}

      <Overrides />
    </Page>
  );
}
