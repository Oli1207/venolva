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
  return (
    <tr>
      <td><b>{u.name}</b><div className="small muted">{u.email || u.phone}{u.commune ? ` · ${u.commune}` : ""}</div></td>
      <td>{u.pro_type ? <>{PRO_LABELS[u.pro_type]} {u.pro_verified ? <Badge tone="ok">Vérifié</Badge> : <Badge tone="warn">En attente</Badge>}</> : <span className="muted">Membre</span>}</td>
      <td>{fmtDateTime(u.date_joined)}</td>
      <td>{!u.is_active && <Badge tone="bad">Suspendu</Badge>} {u.is_staff && <Badge tone="warn">Équipe</Badge>}</td>
      <td style={{ minWidth: 230 }}>
        {self ? <span className="small muted">C'est toi</span> : (
          <div className="adm-actions">
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => patch({ is_active: !u.is_active })}>{u.is_active ? "Suspendre" : "Réactiver"}</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => patch({ is_staff: !u.is_staff })}>{u.is_staff ? "Retirer l'accès équipe" : "Donner l'accès équipe"}</button>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function Users() {
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [staff, setStaff] = useState(false);
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/users/", { q, staff: staff ? "1" : "" });
  return (
    <Page title="Utilisateurs" sub="Suspendre un compte le déconnecte tout de suite. Seul un superutilisateur peut donner l'accès à l'administration.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}><label className="k" htmlFor="uq">Recherche</label><input id="uq" className="input" placeholder="Nom ou numéro" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} /></div>
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
