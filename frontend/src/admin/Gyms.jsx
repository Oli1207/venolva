import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

function Row({ g, onChange }) {
  const { busy, error, run } = useAction();
  const [phone, setPhone] = useState("");
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(false);
  const [t, setT] = useState({ name: g.name, commune: g.commune, address: g.address || "" });
  const saveText = (e) => { e.preventDefault(); run(async () => { await api.patch(`/admin/gyms/${g.id}/`, t); setText(false); await onChange(); }); };
  const save = (body) => run(async () => { await api.patch(`/admin/gyms/${g.id}/`, body); setEditing(false); setPhone(""); await onChange(); });

  return (
    <tr>
      <td>
        {text ? (
          <form onSubmit={saveText} style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 220 }}>
            <input className="input" aria-label="Nom" value={t.name} onChange={(e) => setT({ ...t, name: e.target.value })} />
            <input className="input" aria-label="Commune" value={t.commune} onChange={(e) => setT({ ...t, commune: e.target.value })} />
            <input className="input" aria-label="Adresse" placeholder="Adresse" value={t.address} onChange={(e) => setT({ ...t, address: e.target.value })} />
            <div className="adm-actions"><button className="btn sm" disabled={busy}>Enregistrer</button><button type="button" className="link" onClick={() => setText(false)}>Annuler</button></div>
          </form>
        ) : <><b>{g.name}</b><div className="small muted">{g.commune}{g.address ? ` · ${g.address}` : ""}</div></>}
      </td>
      <td>{g.owner ? <><b>{g.owner.name}</b><div className="small muted">{g.owner.email || g.owner.phone}</div></> : <Badge tone="warn">Sans gérant</Badge>}</td>
      <td>{g.verified ? <Badge tone="ok">Vérifiée</Badge> : <Badge>Non vérifiée</Badge>}</td>
      <td style={{ minWidth: 260 }}>
        {editing ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <input aria-label={`E-mail du gérant de ${g.name}`} className="input" placeholder="E-mail du gérant" value={phone} onChange={(e) => setPhone(e.target.value)} />
            <div className="adm-actions">
              <button type="button" className="btn sm" disabled={busy || !phone} onClick={() => save({ owner_phone: phone })}>Rattacher</button>
              {g.owner && <button type="button" className="link" disabled={busy} onClick={() => save({ owner_phone: "" })}>Détacher le gérant</button>}
              <button type="button" className="link" onClick={() => setEditing(false)}>Annuler</button>
            </div>
          </div>
        ) : (
          <div className="adm-actions">
            <button type="button" className="btn ghost sm" onClick={() => setText(true)}>Modifier</button>
            <button type="button" className="btn ghost sm" onClick={() => setEditing(true)}>Gérant</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => save({ verified: !g.verified })}>{g.verified ? "Retirer la coche" : "Vérifier"}</button>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

function AddGym({ onDone }) {
  const { busy, error, run } = useAction();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", commune: "", address: "" });
  const submit = (e) => { e.preventDefault(); run(async () => { await api.post("/admin/gyms/create/", f); setF({ name: "", commune: "", address: "" }); setOpen(false); await onDone(); }); };
  if (!open) return <button type="button" className="btn" style={{ marginBottom: 14 }} onClick={() => setOpen(true)}>Ajouter une salle</button>;
  return (
    <form className="adm-form" onSubmit={submit} style={{ marginBottom: 14 }}>
      <div className="field"><label className="k" htmlFor="gn">Nom</label><input id="gn" className="input" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
      <div className="field"><label className="k" htmlFor="gc">Commune</label><input id="gc" className="input" required value={f.commune} onChange={(e) => setF({ ...f, commune: e.target.value })} /></div>
      <div className="field"><label className="k" htmlFor="ga">Adresse</label><input id="ga" className="input" value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></div>
      <button className="btn" disabled={busy || !f.name || !f.commune}>Créer la salle</button>
      <button type="button" className="link" onClick={() => setOpen(false)}>Annuler</button>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}

export default function AdminGyms() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/gyms/", { q });
  return (
    <Page title="Salles" sub="Rattache une salle à son gérant : il pourra alors gérer ses horaires, ses formules et ses cours depuis l'app. L'e-mail doit être celui d'un compte existant.">
      <AddGym onDone={reload} />
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}><label className="k" htmlFor="gq">Recherche</label><input id="gq" className="input" placeholder="Nom ou commune" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} /></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Salle</th><th>Gérant</th><th>Statut</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={4}>Chargement…</EmptyRow> : error ? <EmptyRow cols={4}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={4}>Aucune salle.</EmptyRow> : data.results.map((g) => <Row key={g.id} g={g} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
