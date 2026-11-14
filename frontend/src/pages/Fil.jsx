import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { PRO_LABELS, ago, fmtWhen } from "../labels";
import { Avatar, Empty, Icon, Loading, TabBar, Verified } from "../ui";
import { MarcheTab } from "./Marche";

const TABS = [["", "Tout"], ["kind=buddy", "Binômes"], ["pros=1", "Pros"], ["", "Marché"]];
const MARKET = 3;

function Entry({ post, mine }) {
  const nav = useNavigate();
  const { busy, error, run } = useAction();
  const a = post.author;
  const role = a.pro_verified && a.pro_type ? PRO_LABELS[a.pro_type] : null;

  const join = () =>
    run(async () => {
      await api.post(`/posts/${post.id}/join/`);
      const conv = await api.post("/conversations/start/", { user: a.id });
      nav(`/messages/${conv.id}`);
    });

  return (
    <article className="entry">
      <Avatar person={a} size={40} />
      <div className="body">
        <div className="pn">
          {role ? <Link to={`/pros/${a.id}`}>{a.display_name}</Link> : a.display_name || "Membre"}
          {role && <Verified />}
          <span className="pm">· {role || a.commune || "Membre"} · {ago(post.created_at)}</span>
        </div>
        <p className="tx">{post.body}</p>
        {post.kind === "buddy" && (
          <>
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--ink-2)" }}>
              <b style={{ fontWeight: 600 }}>{fmtWhen(post.starts_at)}</b>{post.gym_name ? ` · ${post.gym_name}` : ""}
            </div>
            {!mine && (
              <button type="button" className="act" onClick={join} disabled={busy}>
                <span>{busy ? "Envoi…" : "Je viens"}</span><Icon name="send" size={16} stroke={2.2} />
              </button>
            )}
            {error && <p className="error" role="alert">{error}</p>}
          </>
        )}
      </div>
    </article>
  );
}

export default function Fil() {
  const { user } = useAuth();
  const [tab, setTab] = useState(0);
  const posts = useFetch(`/posts/?${TABS[tab][0]}`, { enabled: tab !== MARKET });
  const convs = useFetch("/conversations/");
  const unread = (convs.data || []).some((c) => c.unread > 0);

  return (
    <main className="page">
      <div className="titlebar">
        <h1 className="h" style={{ fontSize: 32, lineHeight: 1 }}>Fil</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/messages" className="iconbtn" aria-label={unread ? "Messages, nouveaux messages" : "Messages"}>
            <Icon name="chat" size={18} />{unread && <span className="dot" />}
          </Link>
          <Link to={tab === MARKET ? "/vendre" : "/publier"} className="iconbtn dark" aria-label={tab === MARKET ? "Vendre un article" : "Publier"}><Icon name="plus" size={18} stroke={2.4} /></Link>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {TABS.map(([, label], i) => <button key={label} role="tab" aria-selected={tab === i} className={`tab ${tab === i ? "on" : ""}`} onClick={() => setTab(i)}>{label}</button>)}
      </div>
      {tab === 2 && (
        <div className="rows">
          <Link to="/pros" className="row" style={{ minHeight: 60 }}>
            <div style={{ flex: 1 }}><div style={{ fontWeight: 600, fontSize: 15 }}>Trouver un coach ou un pro</div><div className="small muted">Réserve une séance près de chez toi</div></div>
            <Icon name="chevron" size={18} stroke={2} />
          </Link>
          <Link to="/salles" className="row" style={{ minHeight: 60 }}>
            <div style={{ flex: 1 }}><div style={{ fontWeight: 600, fontSize: 15 }}>Trouver une salle</div><div className="small muted">Horaires, tarifs, cours et avis</div></div>
            <Icon name="chevron" size={18} stroke={2} />
          </Link>
        </div>
      )}
      {tab === MARKET ? <MarcheTab /> : posts.loading ? <Loading /> : posts.error ? <Empty title="Impossible de charger le fil">{posts.error.message}</Empty> : posts.data.results.length === 0 ? (
        <Empty title="Rien ici pour l'instant">Sois le premier à publier ou à chercher un binôme.</Empty>
      ) : (
        posts.data.results.map((p) => <Entry key={p.id} post={p} mine={p.author.id === user.id} />)
      )}
      <TabBar />
    </main>
  );
}
