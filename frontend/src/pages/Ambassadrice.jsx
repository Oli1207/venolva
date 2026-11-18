import { useFetch } from "../hooks";
import { fmtDate, fmtPrice } from "../labels";
import { BackButton, Empty, Loading } from "../ui";
import { AccountForm } from "./Revenus";

const STATE = { draft: "À signer", upcoming: "À venir", active: "En cours", ended: "Terminé", terminated: "Résilié" };
const STATEMENT = { pending: "À verser", paid: "Versé" };
const MONTH = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" });

export default function Ambassadrice() {
  const { data, loading, error, reload } = useFetch("/my/ambassador/");
  if (loading && !data) return <main className="page bare"><div className="topbar"><BackButton to="/profil" /></div><Loading /></main>;
  if (error) return <main className="page bare"><div className="topbar"><BackButton to="/profil" /></div><Empty title="Espace réservé aux ambassadrices">{error.message}</Empty></main>;
  const c = data.contract;
  const leaving = c && c.state === "active" && c.days_left <= 30 && !c.renewed;

  return (
    <main className="page bare" style={{ paddingBottom: 40 }}>
      <div className="topbar" style={{ paddingBottom: 12 }}><BackButton to="/profil" /><h1 className="h" style={{ fontSize: 28, lineHeight: 1 }}>Ambassadrice</h1></div>

      {!c ? (
        <Empty title="Pas encore de contrat">L'équipe Venolva va préparer ton contrat. Tu le verras ici dès qu'il sera créé.</Empty>
      ) : (
        <>
          <div className="pad" style={{ paddingTop: 12 }}>
            <div className="k">Gagné et pas encore relevé</div>
            <div className="h" style={{ fontSize: 46, letterSpacing: "-0.05em", lineHeight: 1.05, marginTop: 4 }}>{fmtPrice(c.preview?.amount || 0)}</div>
            <p className="small muted" style={{ margin: "8px 0 0", lineHeight: 1.5 }}>
              {c.state === "draft" ? "Ton contrat n'est pas encore signé : il ne produit pas de gains." : `Estimation à partir de ${fmtPrice(c.preview?.fees || 0)} de commissions de Venolva. Elle est confirmée sur ton relevé du mois.`}
            </p>
          </div>

          <div className="rows" style={{ paddingTop: 20 }}>
            <div className="k" style={{ paddingBottom: 2 }}>Mon contrat</div>
            <div className="cr"><span className="l">État</span><span className="v">{STATE[c.state]}</span></div>
            <div className="cr"><span className="l">Période</span><span className="v">{fmtDate(c.start_date)} → {fmtDate(c.end_date)}</span></div>
            <div className="cr"><span className="l">Ma part</span><span className="v">{c.share_pct} % des commissions</span></div>
            {c.signed_at && <div className="cr"><span className="l">Signé le</span><span className="v">{fmtDate(c.signed_at)}</span></div>}
            {c.days_left != null && <div className="cr"><span className="l">Il reste</span><span className="v">{c.days_left} jour{c.days_left > 1 ? "s" : ""}</span></div>}
          </div>
          {leaving && <div className="callout" style={{ margin: "14px 24px 0" }}>Ton contrat se termine dans {c.days_left} jours. L'équipe te proposera son renouvellement, à signer de nouveau.</div>}

          <p className="hint pad" style={{ margin: "16px 0 0", lineHeight: 1.55 }}>
            Tu touches {c.share_pct} % de la commission que Venolva perçoit sur les paiements en ligne (réservations et cours), une fois la séance passée et le délai d'attente écoulé. Rien n'est retiré à l'argent des pros et des salles, et un paiement remboursé ne compte pas.
          </p>

          <div className="stats" style={{ paddingTop: 20 }}>
            <div className="stat"><div className="sv" style={{ fontSize: 22 }}>{fmtPrice(data.totals.pending)}</div><div className="sl">À te verser</div></div>
            <div className="stat"><div className="sv" style={{ fontSize: 22 }}>{fmtPrice(data.totals.paid)}</div><div className="sl">Déjà versé</div></div>
          </div>
        </>
      )}

      <div style={{ marginTop: 24 }}>
        <div className="k pad" style={{ marginBottom: 4 }}>Mes relevés</div>
        {data.statements.length === 0 ? <p className="hint pad">Ton premier relevé arrive à la fin du premier mois complet.</p> : (
          <div className="rows">
            {data.statements.map((s) => (
              <div key={s.id} className="row" style={{ cursor: "default", minHeight: 64 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, textTransform: "capitalize" }}>{MONTH.format(new Date(s.month))}</div>
                  <div className="small muted">{fmtPrice(s.fees_total)} de commissions × {s.share_pct} %{s.reference ? ` · réf. ${s.reference}` : ""}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="price" style={{ fontSize: 16 }}>{fmtPrice(s.amount)}</div>
                  <div className="small" style={{ fontWeight: 600, color: s.status === "paid" ? "var(--ok)" : "var(--accent-ink)" }}>{STATEMENT[s.status]}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="pad" style={{ paddingTop: 26 }}>
        <div className="k" style={{ marginBottom: 10 }}>Où recevoir mes versements</div>
        <AccountForm account={data.account} onSaved={reload} />
      </div>
    </main>
  );
}
