import { useNavigate } from "react-router-dom";
import { useFetch } from "../hooks";
import { PRO_LABELS, ago } from "../labels";
import { Avatar, BackButton, Empty, Loading, Verified } from "../ui";

export default function Messages() {
  const nav = useNavigate();
  const { data, loading, error } = useFetch("/conversations/");

  return (
    <main className="page bare">
      <div className="topbar" style={{ paddingBottom: 14 }}>
        <BackButton to="/fil" />
        <h1 className="h" style={{ fontSize: 30, lineHeight: 1 }}>Messages</h1>
      </div>
      <div style={{ borderTop: "1px solid var(--line)" }} />
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger les messages">{error.message}</Empty> : data.length === 0 ? (
        <Empty title="Aucun message">Dis bonjour à un binôme pour démarrer une discussion.</Empty>
      ) : data.map((c) => (
        <button key={c.id} type="button" className={`cv ${c.unread ? "unr" : ""}`} onClick={() => nav(`/messages/${c.id}`)}>
          <Avatar person={c.other} size={50} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="nm">{c.other.display_name || "Membre"}</span>
              {c.other.pro_verified && c.other.pro_type && <><Verified /><span className="small muted">{PRO_LABELS[c.other.pro_type]}</span></>}
              <span className="small muted" style={{ marginLeft: "auto", fontWeight: c.unread ? 700 : 400, color: c.unread ? "var(--ink)" : undefined }}>{ago(c.last_at)}</span>
            </div>
            <div className="pv">{c.last_message || "Nouvelle discussion"}</div>
          </div>
          {c.unread > 0 && <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--accent)", flex: "none" }} aria-label={`${c.unread} non lu${c.unread > 1 ? "s" : ""}`} />}
        </button>
      ))}
    </main>
  );
}
