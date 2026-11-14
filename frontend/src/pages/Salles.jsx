import { useState } from "react";
import { Link } from "react-router-dom";
import { useFetch } from "../hooks";
import { COMMUNES } from "../labels";
import { BackButton, Empty, Icon, Loading, Verified } from "../ui";

export function GymTile({ name, size = 48 }) {
  const initials = name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  return <div className="av t3" style={{ width: size, height: size, fontSize: Math.round(size * 0.34) }} aria-hidden="true">{initials}</div>;
}

export default function Salles() {
  const [q, setQ] = useState("");
  const [commune, setCommune] = useState("");
  const qs = new URLSearchParams({ ...(q.trim() ? { q: q.trim() } : {}), ...(commune ? { commune } : {}) }).toString();
  const { data, loading, error } = useFetch(`/gyms/?${qs}`);

  return (
    <main className="page bare">
      <div className="topbar" style={{ paddingBottom: 6 }}>
        <BackButton to="/fil" />
        <h1 className="h" style={{ fontSize: 30, lineHeight: 1 }}>Salles</h1>
      </div>
      <div className="pad" style={{ paddingTop: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="input" style={{ display: "flex", alignItems: "center", gap: 10, height: 46, color: "var(--mute)" }}>
          <Icon name="search" size={18} />
          <input aria-label="Chercher une salle" placeholder="Nom ou commune" value={q} onChange={(e) => setQ(e.target.value)} style={{ border: 0, outline: "none", flex: 1, background: "none", minWidth: 0 }} />
        </div>
        <select aria-label="Commune" className="input" style={{ height: 46 }} value={commune} onChange={(e) => setCommune(e.target.value)}>
          <option value="">Toutes les communes</option>
          {COMMUNES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger les salles">{error.message}</Empty> : data.length === 0 ? (
        <Empty title="Aucune salle trouvée">Essaie une autre commune.</Empty>
      ) : (
        <div className="rows" style={{ paddingTop: 8 }}>
          {data.map((g) => (
            <Link key={g.id} to={`/salles/${g.id}`} className="row" style={{ minHeight: 72 }}>
              <GymTile name={g.name} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 15.5, display: "flex", alignItems: "center", gap: 6 }}>{g.name}{g.verified && <Verified />}</div>
                <div className="small muted" style={{ marginTop: 2 }}>{g.commune} · {g.members_count} membre{g.members_count > 1 ? "s" : ""}</div>
              </div>
              {g.rating_avg != null && <span className="price" style={{ fontSize: 15 }}>{String(g.rating_avg).replace(".", ",")}</span>}
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
