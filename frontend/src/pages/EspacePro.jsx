import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { BookingRow } from "../Bookings";
import { useAction, useFetch } from "../hooks";
import { DAY_NAMES, MODE_LABELS, SERVICE_KINDS, fmtPrice, modesLabel } from "../labels";
import { BackButton, Empty, Loading, Toggle } from "../ui";

function Reservations() {
  const { data, loading, error, reload } = useFetch("/bookings/?role=pro");
  if (loading) return <Loading />;
  if (error) return <Empty title="Impossible de charger les réservations">{error.message}</Empty>;
  const todo = data.filter((b) => b.status === "pending").length;
  return data.length === 0 ? (
    <Empty title="Aucune réservation">Elles apparaîtront ici dès qu'un membre réserve un de tes services.</Empty>
  ) : (
    <>
      {todo > 0 && <p className="pad" style={{ margin: "14px 0 0", fontSize: 14, fontWeight: 600, color: "var(--accent-ink)" }}>{todo} réservation{todo > 1 ? "s" : ""} à confirmer</p>}
      {data.map((b) => <BookingRow key={b.id} b={b} onChange={reload} />)}
    </>
  );
}

function NewService({ onDone }) {
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ name: "", kind: "single", duration_min: 60, price: "", modes: ["gym"], description: "" });
  const set = (p) => setF((x) => ({ ...x, ...p }));
  const toggleMode = (m) => setF((x) => ({ ...x, modes: x.modes.includes(m) ? x.modes.filter((y) => y !== m) : [...x.modes, m] }));
  const submit = (e) => {
    e.preventDefault();
    run(async () => {
      await api.post("/my/services/", { ...f, duration_min: Number(f.duration_min), price: Number(f.price) });
      onDone();
    });
  };
  return (
    <form className="pad" onSubmit={submit} style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="chips">{SERVICE_KINDS.map((k) => <button type="button" key={k.code} className={`chip ${f.kind === k.code ? "on" : ""}`} style={{ height: 36, fontSize: 13.5 }} onClick={() => set({ kind: k.code, name: f.name || k.label })}>{k.label}</button>)}</div>
      <div className="field"><label className="k" htmlFor="sn">Nom du service</label><input id="sn" className="input" maxLength={80} value={f.name} onChange={(e) => set({ name: e.target.value })} /></div>
      <div style={{ display: "flex", gap: 12 }}>
        <div className="field" style={{ flex: 1 }}><label className="k" htmlFor="sd">Durée (min)</label><input id="sd" className="input" type="number" min="15" max="240" step="5" value={f.duration_min} onChange={(e) => set({ duration_min: e.target.value })} /></div>
        <div className="field" style={{ flex: 1 }}><label className="k" htmlFor="sp">Prix (FCFA)</label><input id="sp" className="input" type="number" min="500" step="500" value={f.price} onChange={(e) => set({ price: e.target.value })} /></div>
      </div>
      <div className="field"><span className="k">Où</span><div className="chips">{Object.entries(MODE_LABELS).map(([m, label]) => <button type="button" key={m} aria-pressed={f.modes.includes(m)} className={`chip ${f.modes.includes(m) ? "on" : ""}`} onClick={() => toggleMode(m)}>{label}</button>)}</div></div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn" disabled={busy || f.name.trim().length < 2 || !f.price || f.modes.length === 0}>{busy ? "Publication…" : "Publier le service"}</button>
    </form>
  );
}

function Services() {
  const { data, loading, error, reload } = useFetch("/my/services/");
  const { error: actError, run } = useAction();
  const [adding, setAdding] = useState(false);
  if (loading) return <Loading />;
  if (error) return <Empty title="Impossible de charger tes services">{error.message}</Empty>;
  if (adding) return <NewService onDone={() => { setAdding(false); reload(); }} />;
  return (
    <>
      <div className="rows" style={{ paddingTop: 6 }}>
        {data.length === 0 && <Empty title="Aucun service">Ajoute ton premier service pour pouvoir recevoir des réservations.</Empty>}
        {data.map((s) => (
          <div key={s.id} className="row" style={{ minHeight: 78, cursor: "default" }}>
            <div style={{ flex: 1, minWidth: 0, opacity: s.active ? 1 : 0.5 }}>
              <div style={{ fontWeight: 600, fontSize: 16 }}>{s.name}</div>
              <div className="small muted" style={{ marginTop: 2 }}>{s.duration_min} min · {modesLabel(s.modes)}</div>
              <div className="price" style={{ fontSize: 15, marginTop: 3 }}>{fmtPrice(s.price)}</div>
            </div>
            <Toggle on={s.active} label={`${s.name} actif`} onChange={(v) => run(async () => { await api.patch(`/my/services/${s.id}/`, { active: v }); await reload(); })} />
          </div>
        ))}
      </div>
      {actError && <p className="error pad" role="alert">{actError}</p>}
      <div className="pad" style={{ paddingTop: 16 }}><button type="button" className="btn" onClick={() => setAdding(true)}>Ajouter un service</button></div>
    </>
  );
}

const hhmm = (t) => t.slice(0, 5);

function Hours() {
  const { data, loading, error } = useFetch("/my/availability/");
  const { busy, error: saveError, run } = useAction();
  const [rows, setRows] = useState(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (data) setRows(data.map((r) => ({ weekday: r.weekday, start: hhmm(r.start), end: hhmm(r.end) }))); }, [data]);
  if (loading || !rows) return error ? <Empty title="Impossible de charger tes horaires">{error.message}</Empty> : <Loading />;

  const edit = (i, patch) => { setSaved(false); setRows((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x))); };
  const add = (weekday) => { setSaved(false); setRows((r) => [...r, { weekday, start: "09:00", end: "12:00" }]); };
  const remove = (i) => { setSaved(false); setRows((r) => r.filter((_, j) => j !== i)); };
  return (
    <div className="pad" style={{ paddingTop: 16 }}>
      <p className="hint" style={{ margin: "0 0 10px" }}>Les membres ne peuvent réserver que pendant ces plages.</p>
      {DAY_NAMES.map((name, wd) => {
        const mine = rows.map((r, i) => ({ ...r, i })).filter((r) => r.weekday === wd);
        return (
          <div key={wd} style={{ display: "flex", gap: 12, padding: "12px 0", borderBottom: "1px solid var(--line-2)", alignItems: "flex-start" }}>
            <div style={{ width: 40, fontWeight: 700, fontSize: 15, textTransform: "capitalize", paddingTop: 10 }}>{name}</div>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
              {mine.length === 0 && <span className="muted" style={{ fontSize: 14, paddingTop: 10 }}>Fermé</span>}
              {mine.map((r) => (
                <div key={r.i} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input aria-label={`${name} début`} className="input" type="time" step="900" value={r.start} onChange={(e) => edit(r.i, { start: e.target.value })} style={{ height: 42, padding: "0 10px" }} />
                  <span className="muted">à</span>
                  <input aria-label={`${name} fin`} className="input" type="time" step="900" value={r.end} onChange={(e) => edit(r.i, { end: e.target.value })} style={{ height: 42, padding: "0 10px" }} />
                  <button type="button" className="link" aria-label={`Retirer cette plage du ${name}`} onClick={() => remove(r.i)}>Retirer</button>
                </div>
              ))}
              <button type="button" className="link" style={{ alignSelf: "flex-start" }} onClick={() => add(wd)}>+ Ajouter une plage</button>
            </div>
          </div>
        );
      })}
      {saveError && <p className="error" role="alert">{saveError}</p>}
      <button type="button" className="btn" style={{ margin: "18px 0 28px" }} disabled={busy} onClick={() => run(async () => { await api.put("/my/availability/", rows); setSaved(true); })}>{busy ? "Enregistrement…" : saved ? "Enregistré" : "Enregistrer mes horaires"}</button>
    </div>
  );
}

export default function EspacePro() {
  const { user } = useAuth();
  const [tab, setTab] = useState("bookings");
  if (!user.pro_type || !user.pro_verified) return <Navigate to="/pro/devenir" replace />;
  if (user.pro_type === "gym") return <Navigate to="/ma-salle" replace />; // le gérant de salle a son propre espace
  return (
    <main className="page bare">
      <div className="topbar" style={{ paddingBottom: 14 }}><BackButton to="/profil" /><h1 className="h" style={{ fontSize: 28, lineHeight: 1 }}>Espace pro</h1></div>
      <div className="tabs" role="tablist">
        {[["bookings", "Réservations"], ["services", "Services"], ["hours", "Horaires"]].map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      {tab === "bookings" && <Reservations />}
      {tab === "services" && <Services />}
      {tab === "hours" && <Hours />}
    </main>
  );
}
