import { useState } from "react";
import { Link } from "react-router-dom";
import { useFetch } from "../hooks";
import { PRO_TYPES, fmtPrice } from "../labels";
import { Avatar, BackButton, Empty, Loading, Verified } from "../ui";

export default function Pros() {
  const [type, setType] = useState("");
  const { data, loading, error } = useFetch(`/pros/${type ? `?type=${type}` : ""}`);

  return (
    <main className="page bare">
      <div className="topbar" style={{ paddingBottom: 6 }}>
        <BackButton to="/fil" />
        <h1 className="h" style={{ fontSize: 30, lineHeight: 1 }}>Pros</h1>
      </div>
      <div className="pad" style={{ paddingTop: 14, paddingBottom: 6, display: "flex", gap: 8, overflowX: "auto", scrollbarWidth: "none" }}>
        {[{ code: "", label: "Tous" }, ...PRO_TYPES.filter((t) => ["coach", "nutrition", "physio", "doctor"].includes(t.code))].map((t) => (
          <button key={t.code} type="button" className={`chip ${type === t.code ? "on" : ""}`} style={{ flex: "none", height: 36, fontSize: 13.5 }} onClick={() => setType(t.code)}>{t.label.split(",")[0]}</button>
        ))}
      </div>
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger les pros">{error.message}</Empty> : data.length === 0 ? (
        <Empty title="Aucun pro pour l'instant">Les coachs et nutritionnistes validés apparaîtront ici.</Empty>
      ) : (
        <div className="rows" style={{ paddingTop: 8 }}>
          {data.map((p) => (
            <Link key={p.person.id} to={`/pros/${p.person.id}`} className="row" style={{ minHeight: 76 }}>
              <Avatar person={p.person} size={48} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 15.5, display: "flex", alignItems: "center", gap: 6 }}>{p.person.display_name}<Verified /></div>
                <div className="small muted" style={{ marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.speciality}{p.gym ? ` · ${p.gym}` : p.person.commune ? ` · ${p.person.commune}` : ""}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="k" style={{ fontSize: 10 }}>Dès</div>
                <div className="price" style={{ fontSize: 15 }}>{fmtPrice(p.min_price)}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
