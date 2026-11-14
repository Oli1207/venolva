import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth";
import { useFetch } from "../hooks";
import { Wordmark } from "../ui";

export default function AdminShell() {
  const { user } = useAuth();
  const stats = useFetch("/admin/dashboard/");
  const d = stats.data;
  useEffect(() => { document.title = "Administration · Djinzin"; return () => { document.title = "Djinzin"; }; }, []);

  const items = [
    ["/admin", "Tableau de bord", 0, true],
    ["/admin/reglages", "Réglages", 0],
    ["/admin/paiements", "Paiements", d ? d.refunds.count + d.to_review : 0],
    ["/admin/reversements", "Reversements", 0],
    ["/admin/dossiers", "Dossiers pro", d?.pros_pending || 0],
    ["/admin/salles", "Salles", 0],
    ["/admin/moderation", "Modération", d?.reports_open || 0],
    ["/admin/utilisateurs", "Utilisateurs", 0],
    ["/admin/journal", "Journal", 0],
  ];

  return (
    <div className="adm">
      <aside className="adm-side">
        <div><Wordmark size={22} /><div className="k" style={{ marginTop: 6 }}>Administration</div></div>
        <nav className="adm-nav" aria-label="Administration">
          {items.map(([to, label, count, end]) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? "on" : "")}>
              {label}{count > 0 && <span className="adm-count" aria-label={`${count} à traiter`}>{count}</span>}
            </NavLink>
          ))}
        </nav>
        <div style={{ marginTop: "auto", fontSize: 13, color: "var(--mute)", display: "flex", flexDirection: "column", gap: 6 }}>
          <span>{user.display_name || user.phone}</span>
          <NavLink to="/fil" style={{ textDecoration: "underline", textUnderlineOffset: 3 }}>Retour à l'app</NavLink>
        </div>
      </aside>
      <main className="adm-main"><Outlet context={{ refreshStats: stats.reload }} /></main>
    </div>
  );
}
