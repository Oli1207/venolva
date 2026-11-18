import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useFetch } from "../hooks";
import { ago } from "../labels";
import { BackButton, Empty, Loading } from "../ui";

export default function Notifications() {
  const { data, loading, error } = useFetch("/notifications/");
  // Ouvrir la page marque tout comme lu ; on garde l'affichage « non lu » le temps de la visite.
  useEffect(() => {
    if (data?.unread > 0) api.post("/notifications/read/", { all: true }).catch(() => {});
  }, [data?.unread]);
  return (
    <main className="page bare">
      <div className="topbar"><BackButton to="/fil" /></div>
      <h1 className="h pad" style={{ fontSize: 30, margin: "6px 0 10px" }}>Notifications</h1>
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger">{error.message}</Empty> : data.results.length === 0 ? (
        <Empty title="Rien de nouveau">Tu seras prévenu ici des réservations, séances et paiements.</Empty>
      ) : (
        <div className="rows">
          {data.results.map((n) => {
            const inner = (
              <>
                {!n.read && <span className="unread-dot" aria-label="Non lu" />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: n.read ? 500 : 700, fontSize: 15 }}>{n.title}</div>
                  {n.body && <div className="small muted">{n.body}</div>}
                  <div className="small muted">{ago(n.created_at)}</div>
                </div>
              </>
            );
            return n.link ? <Link key={n.id} to={n.link} className="row" style={{ minHeight: 60 }}>{inner}</Link> : <div key={n.id} className="row" style={{ minHeight: 60, cursor: "default" }}>{inner}</div>;
          })}
        </div>
      )}
    </main>
  );
}
