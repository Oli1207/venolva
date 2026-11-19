import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { fmtDateTime } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

const KIND = { text: "Publication", buddy: "Binôme", article: "Article" };

function Row({ p, onChange }) {
  const { busy, error, run } = useAction();
  const act = (action) => run(async () => { await api.post(`/admin/posts/${p.id}/${action}/`); await onChange(); });
  return (
    <tr>
      <td>{fmtDateTime(p.created_at)}</td>
      <td>
        <Badge>{KIND[p.kind]}</Badge> {p.hidden && <Badge tone="bad">Masquée</Badge>} {p.reports > 0 && <Badge tone="warn">{p.reports} signalement{p.reports > 1 ? "s" : ""}</Badge>}
        {p.title && <div><b>{p.title}</b></div>}
        <div className="small">{p.body}</div>
        <div className="small muted">de {p.author.name} ({p.author.email || p.author.phone})</div>
      </td>
      <td style={{ minWidth: 200 }}>
        <div className="adm-actions">
          {p.hidden ? <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("show")}>Réafficher</button> : <button type="button" className="btn sm" disabled={busy} onClick={() => act("hide")}>Masquer</button>}
          <button type="button" className="btn ghost sm" disabled={busy} onClick={() => window.confirm("Supprimer définitivement cette publication ?") && act("delete")}>Supprimer</button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function Publications() {
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("");
  const [view, setView] = useState("");
  const params = { q, kind, hidden: view === "hidden" ? "1" : "", reported: view === "reported" ? "1" : "" };
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/posts/", params);
  return (
    <Page title="Publications" sub="Toutes les publications et tous les articles. Masquer une publication la retire du fil sans la supprimer ; supprimer est définitif.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}><label className="k" htmlFor="pq">Recherche</label><input id="pq" className="input" placeholder="Texte, auteur ou e-mail" value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} /></div>
        <div className="field"><label className="k" htmlFor="pk">Type</label>
          <select id="pk" className="input" value={kind} onChange={(e) => { setPage(1); setKind(e.target.value); }}><option value="">Tous</option><option value="text">Publications</option><option value="buddy">Binômes</option><option value="article">Articles</option></select></div>
        <div className="field"><label className="k" htmlFor="pv">Afficher</label>
          <select id="pv" className="input" value={view} onChange={(e) => { setPage(1); setView(e.target.value); }}><option value="">Toutes</option><option value="reported">Signalées</option><option value="hidden">Masquées</option></select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Publication</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={3}>Chargement…</EmptyRow> : error ? <EmptyRow cols={3}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={3}>Aucune publication.</EmptyRow> : data.results.map((p) => <Row key={p.id} p={p} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
