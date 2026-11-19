import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction } from "../hooks";
import { PRO_LABELS, fmtDateTime } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

function Row({ u, me, onChange }) {
  const { busy, error, run } = useAction();
  const patch = (body) => run(async () => { await api.patch(`/admin/users/${u.id}/`, body); await onChange(); });
  const self = u.id === me.id;
  const [editing, setEditing] = useState(false);
  const [f, setF] = useState({ email: u.email || "", display_name: u.name === (u.email || u.phone) ? "" : u.name, commune: u.commune || "" });
  const saveIdentity = (e) => { e.preventDefault(); run(async () => { await api.patch(`/admin/users/${u.id}/`, f); setEditing(false); await onChange(); }); };
  return (
    <tr>
      <td>
        {editing ? (
          <form onSubmit={saveIdentity} style={{ display: "flex", flexDirection: "column", gap: 6, minWidth: 240 }}>
            <input className="input" type="email" aria-label="E-mail" placeholder="E-mail" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
            <input className="input" aria-label="Nom" placeholder="Nom" value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} />
            <input className="input" aria-label="Commune" placeholder="Commune" value={f.commune} onChange={(e) => setF({ ...f, commune: e.target.value })} />
            <div className="adm-actions"><button className="btn sm" disabled={busy}>Enregistrer</button><button type="button" className="link" onClick={() => setEditing(false)}>Annuler</button></div>
          </form>
        ) : <><b>{u.name}</b><div className="small muted">{u.email || u.phone || "Sans e-mail"}{u.commune ? ` · ${u.commune}` : ""}</div></>}
      </td>
      <td>{u.pro_type ? <>{PRO_LABELS[u.pro_type]} {u.pro_verified ? <Badge tone="ok">Vérifié</Badge> : <Badge tone="warn">En attente</Badge>}</> : <span className="muted">Membre</span>}</td>
      <td>{fmtDateTime(u.date_joined)}</td>
      <td>{!u.is_active && <Badge tone="bad">Suspendu</Badge>} {u.is_staff && <Badge tone="warn">Équipe</Badge>}</td>
      <td style={{ minWidth: 230 }}>
        {self ? <span className="small muted">C'est toi</span> : (
          <div className="adm-actions">
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => setEditing(true)}>Modifier</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => patch({ is_active: !u.is_active })}>{u.is_active ? "Suspendre" : "Réactiver"}</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => patch({ is_staff: !u.is_staff })}>{u.is_staff ? "Retirer l'accès équipe" : "Donner l'accès équipe"}</button>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

function AddMember({ onDone }) {
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ email: "", display_name: "", commune: "" });
  const [open, setOpen] = useState(false);
  const submit = (e) => { e.preventDefault(); run(async () => { await api.post("/admin/users/create/", f); setF({ email: "", display_name: "", commune: "" }); setOpen(false); await onDone(); }); };
  if (!open) return <button type="button" className="btn" style={{ marginBottom: 14 }} onClick={() => setOpen(true)}>Ajouter un membre</button>;
  return (
    <form className="adm-form" onSubmit={submit} style={{ marginBottom: 14 }}>
      <div className="field"><label className="k" htmlFor="ne">E-mail</label><input id="ne" className="input" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></div>
      <div className="field"><label className="k" htmlFor="nn">Nom</label><input id="nn" className="input" value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></div>
      <div className="field"><label className="k" htmlFor="nc">Commune</label><input id="nc" className="input" value={f.commune} onChange={(e) => setF({ ...f, commune: e.target.value })} /></div>
      <button className="btn" disabled={busy || !f.email}>Créer le compte</button>
      <button type="button" className="link" onClick={() => setOpen(false)}>Annuler</button>
      {error && <p className="error" role="alert">{error}</p>}
      <p className="hint" style={{ flexBasis: "100%", margin: 0 }}>La personne se connecte ensuite avec le code envoyé à cet e-mail.</p>
    </form>
  );
}

export default function Users() {
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [staff, setStaff] = useState(false);
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/users/", { q, staff: staff ? "1" : "" });
  return (
    <Page title="Utilisateurs" sub="Suspendre un compte le déconnecte tout de suite. Seul un superutilisateur peut donner l'accès à l'administration.">
      <AddMember onDone={reload} />
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}><label className="k" htmlFor="uq">Recherche</label><input id="uq" className="input" placeholder="Nom ou e-mail" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} /></div>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14, paddingBottom: 10 }}><input type="checkbox" checked={staff} onChange={(e) => { setPage(1); setStaff(e.target.checked); }} />Équipe seulement</label>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Compte</th><th>Statut pro</th><th>Inscrit le</th><th>État</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={5}>Chargement…</EmptyRow> : error ? <EmptyRow cols={5}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={5}>Aucun compte.</EmptyRow> : data.results.map((u) => <Row key={u.id} u={u} me={me} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
