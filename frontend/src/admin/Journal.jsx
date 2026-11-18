import { useState } from "react";
import { fmtDateTime } from "../labels";
import { EmptyRow, Page, Pager, usePaged } from "./ui";

const ACTIONS = {
  "settings.update": "Réglages modifiés", "commission.set": "Commission définie", "commission.delete": "Commission supprimée",
  "payment.refund": "Remboursement noté", "payment.accept": "Paiement validé à la main", "payout.create": "Reversement créé",
  "payout.paid": "Reversement versé", "payout.cancel": "Reversement annulé", "pro.approve": "Dossier pro validé", "pro.reject": "Dossier pro refusé",
  "gym.update": "Salle modifiée", "ambassador.create": "Ambassadrice ajoutée", "contract.create": "Contrat créé", "contract.sign": "Contrat signé", "contract.renew": "Contrat renouvelé", "contract.terminate": "Contrat résilié", "statement.generate": "Relevé généré", "statement.paid": "Relevé versé", "statement.cancel": "Relevé annulé", "report.hide": "Annonce retirée", "report.dismiss": "Signalement ignoré", "user.update": "Compte modifié",
};

function Detail({ d }) {
  if (d.changes) {
    return <ul style={{ margin: 0, paddingLeft: 18 }}>{Object.entries(d.changes).map(([k, [from, to]]) => <li key={k}><code>{k}</code> : {String(from)} → <b>{String(to)}</b></li>)}</ul>;
  }
  const entries = Object.entries(d);
  return entries.length ? <span className="small">{entries.map(([k, v]) => `${k} : ${v}`).join(" · ")}</span> : <span className="muted">–</span>;
}

export default function Journal() {
  const [action, setAction] = useState("");
  const { data, loading, error, page, setPage, pages } = usePaged("/admin/audit/", { action });
  return (
    <Page title="Journal" sub="Qui a fait quoi, et quand. Chaque action d'administration y est inscrite, avec la valeur avant et après pour les réglages. Il ne peut pas être modifié.">
      <div className="adm-form" style={{ marginBottom: 14 }}>
        <div className="field"><label className="k" htmlFor="ja">Type</label>
          <select id="ja" className="input" value={action} onChange={(e) => { setPage(1); setAction(e.target.value); }}>
            <option value="">Tout</option><option value="settings">Réglages</option><option value="commission">Commissions</option><option value="payment">Paiements</option><option value="payout">Reversements</option><option value="pro">Dossiers pro</option><option value="gym">Salles</option><option value="ambassador">Ambassadeurs</option><option value="contract">Contrats</option><option value="statement">Relevés</option><option value="report">Modération</option><option value="user">Utilisateurs</option>
          </select></div>
      </div>
      <div className="tbl-wrap">
        <table className="t">
          <thead><tr><th>Date</th><th>Auteur</th><th>Action</th><th>Cible</th><th>Détail</th></tr></thead>
          <tbody>
            {loading && !data ? <EmptyRow cols={5}>Chargement…</EmptyRow> : error ? <EmptyRow cols={5}>{error.message}</EmptyRow> : data.results.length === 0 ? <EmptyRow cols={5}>Rien d'enregistré pour l'instant.</EmptyRow> : data.results.map((a) => (
              <tr key={a.id}><td>{fmtDateTime(a.created_at)}</td><td>{a.actor ? <b>{a.actor.name}</b> : <span className="muted">Compte supprimé</span>}</td><td>{ACTIONS[a.action] || a.action}</td><td className="small">{a.target || "–"}</td><td><Detail d={a.detail} /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {data && <Pager page={page} pages={pages} setPage={setPage} count={data.count} />}
    </Page>
  );
}
