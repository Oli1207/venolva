import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { COMMUNES, DAY_FULL, ago, dayParts, defaultLocalInput, fmtPrice, fmtTime, localToIso } from "../labels";
import { Avatar, BackButton, Empty, Loading, Toggle } from "../ui";

const t5 = (t) => (t || "").slice(0, 5);

function CreateGym({ onDone }) {
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ name: "", commune: "", address: "" });
  const submit = (e) => { e.preventDefault(); run(async () => { await api.post("/my/gym/", f); await onDone(); }); };
  return (
    <form className="pad" onSubmit={submit} style={{ paddingTop: 20, display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ margin: 0, fontSize: 15, lineHeight: 1.5, color: "#55554f" }}>Crée la fiche de ta salle. Tu pourras ensuite ajouter tes horaires, tes formules et tes cours.</p>
      <div className="field"><label className="k" htmlFor="gn">Nom de la salle</label><input id="gn" className="input" maxLength={120} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
      <div className="field"><label className="k" htmlFor="gc">Commune</label><select id="gc" className="input" value={f.commune} onChange={(e) => setF({ ...f, commune: e.target.value })}><option value="">Choisir</option>{COMMUNES.map((c) => <option key={c}>{c}</option>)}</select></div>
      <div className="field"><label className="k" htmlFor="ga">Adresse</label><input id="ga" className="input" maxLength={200} placeholder="Rue, quartier" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="btn" disabled={busy || f.name.trim().length < 2 || !f.commune}>{busy ? "Création…" : "Créer ma salle"}</button>
    </form>
  );
}

function Infos({ gym, reload }) {
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ name: gym.name, commune: gym.commune, address: gym.address, description: gym.description, equipment: gym.equipment.join(", ") });
  const [hours, setHours] = useState(() => DAY_FULL.map((_, wd) => {
    const h = gym.hours.find((x) => x.weekday === wd);
    return { open: !!h, opens: h ? t5(h.opens) : "06:00", closes: h ? t5(h.closes) : "21:00" };
  }));
  const [saved, setSaved] = useState(false);
  const touch = (fn) => { setSaved(false); fn(); };

  const save = () => run(async () => {
    const equipment = f.equipment.split(",").map((s) => s.trim()).filter(Boolean);
    await api.patch("/my/gym/", { name: f.name.trim(), commune: f.commune, address: f.address.trim(), description: f.description.trim(), equipment });
    await api.put("/my/gym/hours/", hours.map((h, weekday) => ({ ...h, weekday })).filter((h) => h.open).map(({ weekday, opens, closes }) => ({ weekday, opens, closes })));
    await reload();
    setSaved(true);
  });

  return (
    <div className="pad" style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="field"><label className="k" htmlFor="n">Nom</label><input id="n" className="input" maxLength={120} value={f.name} onChange={(e) => touch(() => setF({ ...f, name: e.target.value }))} /></div>
      <div className="field"><label className="k" htmlFor="c">Commune</label><select id="c" className="input" value={f.commune} onChange={(e) => touch(() => setF({ ...f, commune: e.target.value }))}>{COMMUNES.map((c) => <option key={c}>{c}</option>)}</select></div>
      <div className="field"><label className="k" htmlFor="a">Adresse</label><input id="a" className="input" maxLength={200} value={f.address} onChange={(e) => touch(() => setF({ ...f, address: e.target.value }))} /></div>
      <div className="field"><label className="k" htmlFor="d">Présentation</label><textarea id="d" className="input" rows={3} maxLength={500} value={f.description} onChange={(e) => touch(() => setF({ ...f, description: e.target.value }))} /></div>
      <div className="field"><label className="k" htmlFor="e">Équipements</label><input id="e" className="input" placeholder="Musculation, Cardio, Douches" value={f.equipment} onChange={(e) => touch(() => setF({ ...f, equipment: e.target.value }))} /><span className="hint">Sépare-les par des virgules (12 au maximum).</span></div>

      <div>
        <div className="k" style={{ marginBottom: 4 }}>Horaires</div>
        {hours.map((h, wd) => (
          <div key={wd} style={{ display: "flex", alignItems: "center", gap: 10, minHeight: 52, borderBottom: "1px solid var(--line-2)" }}>
            <span style={{ width: 82, fontWeight: 600, fontSize: 14.5, textTransform: "capitalize" }}>{DAY_FULL[wd]}</span>
            {h.open ? (
              <>
                <input aria-label={`${DAY_FULL[wd]} ouverture`} type="time" className="input" style={{ height: 40, padding: "0 8px", flex: 1, minWidth: 0 }} value={h.opens} onChange={(e) => touch(() => setHours(hours.map((x, i) => (i === wd ? { ...x, opens: e.target.value } : x))))} />
                <span className="muted">à</span>
                <input aria-label={`${DAY_FULL[wd]} fermeture`} type="time" className="input" style={{ height: 40, padding: "0 8px", flex: 1, minWidth: 0 }} value={h.closes} onChange={(e) => touch(() => setHours(hours.map((x, i) => (i === wd ? { ...x, closes: e.target.value } : x))))} />
              </>
            ) : <span className="muted" style={{ flex: 1 }}>Fermé</span>}
            <Toggle on={h.open} label={`${DAY_FULL[wd]} ouvert`} onChange={(v) => touch(() => setHours(hours.map((x, i) => (i === wd ? { ...x, open: v } : x))))} />
          </div>
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <button type="button" className="btn" disabled={busy} onClick={save} style={{ marginBottom: 28 }}>{busy ? "Enregistrement…" : saved ? "Enregistré" : "Enregistrer"}</button>
    </div>
  );
}

function Plans() {
  const { data, loading, error, reload } = useFetch("/my/gym/plans/");
  const { busy, error: actError, run } = useAction();
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState({ name: "", description: "", price: "" });
  if (loading) return <Loading />;
  if (error) return <Empty title="Impossible de charger les formules">{error.message}</Empty>;
  const create = (e) => { e.preventDefault(); run(async () => { await api.post("/my/gym/plans/", { ...f, price: Number(f.price) }); setF({ name: "", description: "", price: "" }); setAdding(false); await reload(); }); };

  return (
    <>
      <div className="rows" style={{ paddingTop: 6 }}>
        {data.length === 0 && !adding && <Empty title="Aucune formule">Ajoute tes tarifs : séance, mensuel, trimestriel…</Empty>}
        {data.map((p) => (
          <div key={p.id} className="row" style={{ minHeight: 76, cursor: "default" }}>
            <div style={{ flex: 1, minWidth: 0, opacity: p.active ? 1 : 0.5 }}>
              <div style={{ fontWeight: 600, fontSize: 16 }}>{p.name}</div>
              <div className="small muted" style={{ marginTop: 2 }}>{p.description}</div>
              <div className="price" style={{ fontSize: 15, marginTop: 3 }}>{fmtPrice(p.price)}</div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
              <Toggle on={p.active} label={`${p.name} actif`} onChange={(v) => run(async () => { await api.patch(`/my/gym/plans/${p.id}/`, { active: v }); await reload(); })} />
              <button type="button" className="link" onClick={() => run(async () => { await api.del(`/my/gym/plans/${p.id}/`); await reload(); })}>Supprimer</button>
            </div>
          </div>
        ))}
      </div>
      {actError && <p className="error pad" role="alert">{actError}</p>}
      {adding ? (
        <form className="pad" onSubmit={create} style={{ paddingTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="field"><label className="k" htmlFor="pn">Nom</label><input id="pn" className="input" maxLength={60} placeholder="Mensuel" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div className="field"><label className="k" htmlFor="pd">Description</label><input id="pd" className="input" maxLength={120} placeholder="Accès illimité · 30 jours" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></div>
          <div className="field"><label className="k" htmlFor="pp">Prix (FCFA)</label><input id="pp" className="input" type="number" min="500" step="500" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></div>
          <button className="btn" disabled={busy || f.name.trim().length < 2 || !f.price}>Ajouter la formule</button>
        </form>
      ) : <div className="pad" style={{ paddingTop: 16 }}><button type="button" className="btn" onClick={() => setAdding(true)}>Ajouter une formule</button></div>}
    </>
  );
}

function Participants({ id }) {
  const { data, loading } = useFetch(`/my/gym/classes/${id}/participants/`);
  if (loading) return <Loading />;
  return data.length === 0 ? <p className="hint" style={{ margin: "6px 0 0" }}>Aucune réservation pour l'instant.</p> : (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>{data.map((p) => <span key={p.id} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13.5, fontWeight: 500 }}><Avatar person={p} size={26} />{p.display_name}</span>)}</div>
  );
}

function Classes() {
  const { data, loading, error, reload } = useFetch("/my/gym/classes/");
  const { busy, error: actError, run } = useAction();
  const [adding, setAdding] = useState(false);
  const [open, setOpen] = useState(null);
  const [f, setF] = useState({ name: "", when: defaultLocalInput(48), duration_min: 60, capacity: 10, price: 0 });
  if (loading) return <Loading />;
  if (error) return <Empty title="Impossible de charger les cours">{error.message}</Empty>;
  const create = (e) => {
    e.preventDefault();
    run(async () => {
      await api.post("/my/gym/classes/", { name: f.name.trim(), starts_at: localToIso(f.when), duration_min: Number(f.duration_min), capacity: Number(f.capacity), price: Number(f.price) });
      setAdding(false);
      setF({ ...f, name: "" });
      await reload();
    });
  };
  const live = data.filter((c) => c.active);

  return (
    <>
      {live.length === 0 && !adding && <Empty title="Aucun cours">Programme un cours collectif pour que les membres réservent leur place.</Empty>}
      {live.map((c) => {
        const { day, weekday } = dayParts(c.starts_at);
        const booked = c.capacity - c.spots_left;
        return (
          <div key={c.id} className="se" style={{ alignItems: "flex-start" }}>
            <div className="dt"><div className="dd">{day}</div><div className="dw">{weekday}</div></div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{fmtTime(c.starts_at)} · {c.name}</div>
              <div className="small muted" style={{ marginTop: 3 }}>{booked} / {c.capacity} places · {c.price ? fmtPrice(c.price) : "Inclus"}</div>
              <div style={{ display: "flex", gap: 14, marginTop: 8 }}>
                <button type="button" className="link" aria-expanded={open === c.id} onClick={() => setOpen(open === c.id ? null : c.id)}>{open === c.id ? "Masquer" : "Participants"}</button>
                <button type="button" className="link" disabled={busy} onClick={() => run(async () => { await api.del(`/my/gym/classes/${c.id}/`); await reload(); })}>Annuler le cours</button>
              </div>
              {open === c.id && <Participants id={c.id} />}
            </div>
          </div>
        );
      })}
      {actError && <p className="error pad" role="alert">{actError}</p>}
      {adding ? (
        <form className="pad" onSubmit={create} style={{ paddingTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="field"><label className="k" htmlFor="cn">Nom du cours</label><input id="cn" className="input" maxLength={80} placeholder="Zumba et renfo" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div className="field"><label className="k" htmlFor="cw">Quand</label><input id="cw" className="input" type="datetime-local" value={f.when} onChange={(e) => setF({ ...f, when: e.target.value })} /></div>
          <div style={{ display: "flex", gap: 10 }}>
            <div className="field" style={{ flex: 1 }}><label className="k" htmlFor="cd">Durée (min)</label><input id="cd" className="input" type="number" min="15" max="240" value={f.duration_min} onChange={(e) => setF({ ...f, duration_min: e.target.value })} /></div>
            <div className="field" style={{ flex: 1 }}><label className="k" htmlFor="cp">Places</label><input id="cp" className="input" type="number" min="1" max="200" value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></div>
          </div>
          <div className="field"><label className="k" htmlFor="cf">Prix (FCFA, 0 si inclus)</label><input id="cf" className="input" type="number" min="0" step="500" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></div>
          <button className="btn" disabled={busy || f.name.trim().length < 2}>Programmer le cours</button>
        </form>
      ) : <div className="pad" style={{ paddingTop: 16 }}><button type="button" className="btn" onClick={() => setAdding(true)}>Programmer un cours</button></div>}
    </>
  );
}

function Requests() {
  const { data, loading, error, reload } = useFetch("/my/gym/requests/");
  const { busy, error: actError, run } = useAction();
  if (loading) return <Loading />;
  if (error) return <Empty title="Impossible de charger les demandes">{error.message}</Empty>;
  if (data.length === 0) return <Empty title="Aucune demande">Les membres qui veulent une formule apparaîtront ici.</Empty>;
  const label = { pending: "En attente", accepted: "Acceptée", declined: "Refusée", cancelled: "Annulée" };
  return (
    <>
      {data.map((r) => (
        <div key={r.id} className="se" style={{ alignItems: "flex-start" }}>
          <Avatar person={r.user} size={44} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 15.5 }}>{r.user.display_name}</div>
            <div style={{ fontSize: 13.5, color: "#55554f", marginTop: 3 }}>{r.plan.name} · {fmtPrice(r.plan.price)} · {ago(r.created_at)}</div>
            {r.status === "pending" ? (
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button type="button" className="btn sm" disabled={busy} onClick={() => run(async () => { await api.post(`/my/gym/requests/${r.id}/accept/`); await reload(); })}>Accepter</button>
                <button type="button" className="btn ghost sm" disabled={busy} onClick={() => run(async () => { await api.post(`/my/gym/requests/${r.id}/decline/`); await reload(); })}>Refuser</button>
              </div>
            ) : <div className="small" style={{ marginTop: 6, fontWeight: 600, color: r.status === "accepted" ? "var(--ok)" : "var(--mute)" }}>{label[r.status]}</div>}
          </div>
        </div>
      ))}
      {actError && <p className="error pad" role="alert">{actError}</p>}
    </>
  );
}

export default function MaSalle() {
  const gym = useFetch("/my/gym/");
  const [tab, setTab] = useState("infos");
  useEffect(() => { document.title = "Ma salle · Djinzin"; return () => { document.title = "Djinzin"; }; }, []);

  const header = (
    <div className="topbar" style={{ paddingBottom: 14 }}><BackButton to="/profil" /><h1 className="h" style={{ fontSize: 28, lineHeight: 1 }}>Ma salle</h1></div>
  );
  if (gym.loading) return <main className="page bare">{header}<Loading /></main>;
  if (gym.error?.status === 404) return <main className="page bare">{header}<CreateGym onDone={gym.reload} /></main>;
  if (gym.error?.status === 403) return <main className="page bare">{header}<Empty title="Réservé aux gérants">Envoie un dossier « Salle de sport » pour gérer ta salle sur Djinzin.<div style={{ marginTop: 16 }}><Link to="/pro/devenir" className="btn sm">Devenir pro</Link></div></Empty></main>;
  if (gym.error) return <main className="page bare">{header}<Empty title="Impossible de charger ta salle">{gym.error.message}</Empty></main>;

  return (
    <main className="page bare">
      {header}
      <div className="tabs" role="tablist">
        {[["infos", "Infos"], ["plans", "Formules"], ["classes", "Cours"], ["requests", "Demandes"]].map(([k, label]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{label}</button>)}
      </div>
      <div className="pad" style={{ paddingTop: 12 }}><Link to={`/salles/${gym.data.id}`} className="link">Voir ma page publique</Link></div>
      {tab === "infos" && <Infos gym={gym.data} reload={gym.reload} />}
      {tab === "plans" && <Plans />}
      {tab === "classes" && <Classes />}
      {tab === "requests" && <Requests />}
    </main>
  );
}
