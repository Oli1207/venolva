import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useFetch } from "../hooks";
import { Wordmark } from "../ui";

export default function AdminShell() {
  const { user } = useAuth();
  const stats = useFetch("/admin/dashboard/");
  const d = stats.data;
  useEffect(() => { document.title = "Administration · Venolva"; return () => { document.title = "Venolva"; }; }, []);

  // Une entrée sans lien est un titre de section.
  const items = [
    ["/admin", "Tableau de bord", 0, true],
    [null, "Argent"],
    ["/admin/paiements", "Paiements", d ? d.refunds.count + d.to_review : 0],
    ["/admin/reversements", "Reversements", 0],
    ["/admin/reglages", "Réglages", 0],
    ["/admin/ambassadeurs", "Ambassadeurs", d?.ambassador_contracts_ending || 0],
    [null, "Communauté"],
    ["/admin/utilisateurs", "Utilisateurs", 0],
    ["/admin/dossiers", "Dossiers pro", d?.pros_pending || 0],
    ["/admin/salles", "Salles", 0],
    ["/admin/reservations", "Réservations", 0],
    [null, "Contenus"],
    ["/admin/publications", "Publications", 0],
    ["/admin/annonces", "Annonces", 0],
    ["/admin/a-la-une", "À la une", d?.features_pending || 0],
    [null, "Modération"],
    ["/admin/signalements", "Signalements", d?.content_reports_open || 0],
    ["/admin/moderation", "Annonces signalées", d?.reports_open || 0],
    ["/admin/journal", "Journal", 0],
  ];

  return (
    <div className="adm">
      <aside className="adm-side">
        <div><Wordmark size={22} /><div className="k" style={{ marginTop: 6 }}>Administration</div></div>
        <nav className="adm-nav" aria-label="Administration">
          {items.map(([to, label, count, end]) => (to === null ? <div key={label} className="k" style={{ padding: "14px 12px 4px" }}>{label}</div> : (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "on" : "")}>
              {label}{count > 0 && <span className="adm-count" aria-label={`${count} à traiter`}>{count}</span>}
            </NavLink>
          )))}
        </nav>
        <div style={{ marginTop: "auto", fontSize: 13, color: "var(--mute)", display: "flex", flexDirection: "column", gap: 6 }}>
          <span>{user.display_name || user.email}</span>
          <NavLink to="/fil" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>Retour à l'app</NavLink>
        </div>
      </aside>
      <main className="adm-main"><Outlet context={{ refreshStats: stats.reload }} /></main>
    </div>
  );
}
