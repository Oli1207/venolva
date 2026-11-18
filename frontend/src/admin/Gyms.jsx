import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

function Row({ g, onChange }) {
  const { busy, error, run } = useAction();
  const [phone, setPhone] = useState("");
  const [editing, setEditing] = useState(false);
  const save = (body) => run(async () => { await api.patch(`/admin/gyms/${g.id}/`, body); setEditing(false); setPhone(""); await onChange(); });

  return (
    <tr>
      <td><b>{g.name}</b><div className="small muted">{g.commune}{g.address ? ` · ${g.address}` : ""}</div></td>
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
            <button type="button" className="btn ghost sm" onClick={() => setEditing(true)}>Gérant</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => save({ verified: !g.verified })}>{g.verified ? "Retirer la coche" : "Vérifier"}</button>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function AdminGyms() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/gyms/", { q });
  return (
    <Page title="Salles" sub="Rattache une salle à son gérant : il pourra alors gérer ses horaires, ses formules et ses cours depuis l'app. L'e-mail doit être celui d'un compte existant.">
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
