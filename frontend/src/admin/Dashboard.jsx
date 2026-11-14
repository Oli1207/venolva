import { Link } from "react-router-dom";
import { useFetch } from "../hooks";
import { fmtPrice } from "../labels";
import { Loading } from "../ui";
import { Page } from "./ui";

function Tile({ value, label, to, alert }) {
  const body = (<><span className="tv">{value}</span><span className="tl">{label}</span></>);
  return to ? <Link to={to} className={`tile ${alert ? "alert" : ""}`}>{body}</Link> : <div className={`tile ${alert ? "alert" : ""}`}>{body}</div>;
}

export default function Dashboard() {
  const { data: d, loading, error } = useFetch("/admin/dashboard/");
  if (loading) return <Loading />;
  if (error) return <p className="error">{error.message}</p>;

  return (
    <Page title="Tableau de bord" sub="Ce qui demande ton attention, et l'état des paiements sur les 30 derniers jours.">
      {!d.commission_set && (
        <div className="confirm" style={{ marginTop: 0, marginBottom: 22 }}>
          <b>La commission est à 0 %.</b> Djinzin ne retient rien sur les paiements. <Link to="/admin/reglages" style={{ textDecoration: "underline" }}>Régler la commission</Link>
        </div>
      )}

      <div className="adm-section" style={{ marginTop: 0 }}>
        <h2>À traiter</h2>
        <div className="tiles">
          <Tile value={d.pros_pending} label="Dossiers pro à valider" to="/admin/dossiers" alert={d.pros_pending > 0} />
          <Tile value={d.reports_open} label="Annonces signalées" to="/admin/moderation" alert={d.reports_open > 0} />
          <Tile value={d.refunds.count} label={`Remboursements à faire (${fmtPrice(d.refunds.amount)})`} to="/admin/paiements" alert={d.refunds.count > 0} />
          <Tile value={d.to_review} label="Paiements à vérifier" to="/admin/paiements" alert={d.to_review > 0} />
        </div>
      </div>

      <div className="adm-section">
        <h2>Argent, 30 jours</h2>
        <div className="tiles">
          <Tile value={fmtPrice(d.payments_30d.gross)} label={`Encaissé (${d.payments_30d.count} paiements)`} />
          <Tile value={fmtPrice(d.payments_30d.fees)} label="Commission Djinzin" />
          <Tile value={fmtPrice(d.payouts.available)} label="Disponible à reverser" to="/admin/reversements" alert={d.payouts.available > 0} />
          <Tile value={fmtPrice(d.payouts.pending)} label="Reversements à verser" to="/admin/reversements" />
          <Tile value={fmtPrice(d.payouts.paid_total)} label="Déjà reversé, au total" />
        </div>
      </div>

      <div className="adm-section">
        <h2>Communauté</h2>
        <div className="tiles">
          <Tile value={d.users} label={`Membres (+${d.new_users_7d} en 7 jours)`} to="/admin/utilisateurs" />
          <Tile value={d.listings_active} label="Annonces en vente" />
        </div>
      </div>
    </Page>
  );
}
