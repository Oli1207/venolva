import { useState } from "react";
import { Link } from "react-router-dom";
import { useFetch } from "../hooks";
import { CATEGORIES, fmtPrice } from "../labels";
import { BackButton, Empty, Icon, Loading } from "../ui";

export function Photo({ src, alt = "", size = 44 }) {
  return src ? (
    <img src={src} alt={alt} loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
  ) : (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#8b8b84" strokeWidth="1.2" strokeLinecap="round" aria-hidden="true"><path d="M3 9v6M6 6v12M18 6v12M21 9v6M6 12h12" /></svg>
  );
}

export function ListingGrid({ items, showStatus }) {
  return (
    <div className="grid2">
      {items.map((l) => (
        <Link key={l.id} to={`/marche/${l.id}`} className="gcard">
          <div className="gimg">
            <Photo src={l.photos[0]} alt={l.title} />
            {showStatus && l.status !== "active" && <span className="gbadge">{l.status === "sold" ? "Vendu" : "Retiré"}</span>}
          </div>
          <div className="gti">{l.title}</div>
          <div className="price" style={{ fontSize: 16, marginTop: 2 }}>{fmtPrice(l.price)}</div>
          <div className="gme">{l.seller.commune || "Abidjan"} · {l.seller.display_name}</div>
        </Link>
      ))}
    </div>
  );
}

// Contenu de l'onglet Marché du fil : catégories, recherche, grille.
export function MarcheTab() {
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const qs = new URLSearchParams({ ...(category ? { category } : {}), ...(q.trim() ? { q: q.trim() } : {}) }).toString();
  const { data, loading, error } = useFetch(`/listings/?${qs}`);

  return (
    <>
      <div className="pad" style={{ paddingTop: 14 }}>
        <div className="input" style={{ display: "flex", alignItems: "center", gap: 10, height: 46, color: "var(--mute)" }}>
          <Icon name="search" size={18} />
          <input aria-label="Chercher un article" placeholder="Chercher un article" value={q} onChange={(e) => setQ(e.target.value)} style={{ border: 0, outline: "none", flex: 1, background: "none", minWidth: 0 }} />
        </div>
      </div>
      <div className="pad" style={{ paddingTop: 12, display: "flex", gap: 8, overflowX: "auto", scrollbarWidth: "none" }}>
        {[{ code: "", label: "Tout" }, ...CATEGORIES].map((c) => (
          <button key={c.code} type="button" className={`chip ${category === c.code ? "on" : ""}`} style={{ flex: "none", height: 34, fontSize: 13 }} aria-pressed={category === c.code} onClick={() => setCategory(c.code)}>{c.label}</button>
        ))}
      </div>
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger le marché">{error.message}</Empty> : data.results.length === 0 ? (
        <Empty title="Aucun article">
          {q || category ? "Essaie une autre recherche." : "Sois le premier à vendre quelque chose."}
          <div style={{ marginTop: 16 }}><Link to="/vendre" className="btn ghost sm">Vendre un article</Link></div>
        </Empty>
      ) : <ListingGrid items={data.results} />}
    </>
  );
}

export default function MesAnnonces() {
  const { data, loading, error } = useFetch("/listings/?mine=1");
  return (
    <main className="page bare">
      <div className="topbar" style={{ paddingBottom: 10 }}>
        <BackButton to="/profil" />
        <h1 className="h" style={{ fontSize: 28, lineHeight: 1 }}>Mes annonces</h1>
      </div>
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger tes annonces">{error.message}</Empty> : data.results.length === 0 ? (
        <Empty title="Tu ne vends rien pour l'instant">
          Revends ton matériel à d'autres membres.
          <div style={{ marginTop: 16 }}><Link to="/vendre" className="btn sm">Vendre un article</Link></div>
        </Empty>
      ) : <div style={{ paddingTop: 14 }}><ListingGrid items={data.results} showStatus /></div>}
    </main>
  );
}
