import { useState } from "react";
import { api } from "../api";
import { useAction } from "../hooks";
import { fmtDateTime } from "../labels";
import { Badge, EmptyRow, Page, Pager, usePaged } from "./ui";

function Row({ r, onChange }) {
  const { busy, error, run } = useAction();
  const act = (action) => run(async () => { await api.post(`/admin/content-reports/${r.id}/${action}/`); await onChange(); });
  const who = r.kind === "user" ? r.user : r.post?.author;
  return (
    <tr>
      <td>{fmtDateTime(r.created_at)}</td>
      <td>
        {r.kind === "user" ? <><b>Membre : {r.user?.name}</b><div className="small muted">{r.user?.email || r.user?.phone}</div></> : (
          <><b>{r.post?.title || "Publication"}</b><div className="small">{r.post?.body}</div><div className="small muted">de {r.post?.author.name}{r.post?.hidden ? " · déjà masquée" : ""}</div></>
        )}
      </td>
      <td><b>{r.reason_label}</b>{r.detail && <div className="small">{r.detail}</div>}<div className="small muted">par {r.reporter.name}{r.same_target_reports > 1 ? ` · ${r.same_target_reports} signalements au total` : ""}</div></td>
      <td>
        {r.handled ? <Badge>Traité</Badge> : (
          <div className="adm-actions">
            {r.kind === "post" && !r.post?.hidden && <button type="button" className="btn sm" disabled={busy} onClick={() => act("hide_post")}>Masquer la publication</button>}
            <button type="button" className="btn sm" disabled={busy} onClick={() => window.confirm(`Suspendre ${who?.name} ? Il ne pourra plus se connecter.`) && act("suspend_user")}>Suspendre le compte</button>
            <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("dismiss")}>Ignorer</button>
          </div>
        )}
        {error && <p className="error" role="alert">{error}</p>}
      </td>
    </tr>
  );
}

export default function Signalements() {
  const [handled, setHandled] = useState("0");
  const { data, loading, error, reload, page, setPage, pages } = usePaged("/admin/content-reports/", { handled });
  return (
    <Page title="Signalements" sub="Les membres et publications signalés. Une décision clôt tous les signalements sur le même contenu.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field"><label className="k" htmlFor="hs">Afficher</label>
          <select id="hs" className="input" value={handled} onChange={(e) => { setPage(1); setHandled(e.target.value); }}><option value="0">À traiter</option><option value="1">Traités</option></select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Contenu</th><th>Signalement</th><th /></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={4}>Chargement…</EmptyRow> : error ? <EmptyRow cols={4}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={4}>Rien à traiter.</EmptyRow> : data.results.map((r) => <Row key={r.id} r={r} onChange={reload} />)}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
