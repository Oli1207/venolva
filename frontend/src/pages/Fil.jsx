import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { PRO_LABELS, ago, fmtWhen } from "../labels";
import { ReportSheet, Sheet, blockMember } from "../Safety";
import { Avatar, Empty, Icon, Loading, TabBar, Verified } from "../ui";
import { MarcheTab } from "./Marche";

const TABS = [["", "Tout"], ["kind=buddy", "Binômes"], ["pros=1", "Pros"], ["", "Marché"]];
const MARKET = 3;

// Menu « … » d'une publication : supprimer la mienne, ou signaler / bloquer l'auteur.
export function PostMenu({ post, onGone }) {
  const [open, setOpen] = useState(false);
  const [report, setReport] = useState(false);
  const { busy, error, run } = useAction();
  const done = () => { setOpen(false); onGone?.(post.id); };
  return (
    <>
      <button type="button" className="more" aria-label="Plus d'options" onClick={() => setOpen(true)}><Icon name="more" size={20} stroke={2.4} /></button>
      {open && !report && (
        <Sheet onClose={() => setOpen(false)}>
          {post.mine ? (
            <button type="button" className="opt danger" disabled={busy} onClick={() => run(async () => { await api.del(`/posts/${post.id}/`); done(); })}>Supprimer ma publication</button>
          ) : (
            <>
              <button type="button" className="opt" onClick={() => setReport(true)}>Signaler cette publication</button>
              <button type="button" className="opt danger" disabled={busy} onClick={() => run(async () => { await blockMember(post.author.id); done(); })}>Bloquer {post.author.display_name || "ce membre"}</button>
            </>
          )}
          {error && <p className="error" role="alert">{error}</p>}
        </Sheet>
      )}
      {report && <ReportSheet kind="post" target={post.id} onClose={() => { setReport(false); setOpen(false); }} />}
    </>
  );
}

export function LikeButton({ post }) {
  const [s, setS] = useState({ likes: post.likes, liked: post.liked });
  const toggle = async () => {
    const was = s;
    setS({ likes: s.likes + (s.liked ? -1 : 1), liked: !s.liked });
    try { setS(await (was.liked ? api.del : api.post)(`/posts/${post.id}/like/`)); } catch { setS(was); }
  };
  return (
    <button type="button" className={`like ${s.liked ? "on" : ""}`} aria-pressed={s.liked} aria-label={s.liked ? "Retirer mon j'aime" : "J'aime"} onClick={toggle}>
      <Icon name="heart" size={18} stroke={2} />{s.likes > 0 && <span>{s.likes}</span>}
    </button>
  );
}

function Entry({ post, onGone }) {
  const nav = useNavigate();
  const { busy, error, run } = useAction();
  const a = post.author;
  const role = a.pro_verified && a.pro_type ? PRO_LABELS[a.pro_type] : null;
  const article = post.kind === "article";

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
          <PostMenu post={post} onGone={onGone} />
        </div>
        {article && <span className="tag">Article</span>}
        {article && <Link to={`/publication/${post.id}`} className="ttl">{post.title}</Link>}
        <p className="tx">{post.body}</p>
        {article && post.truncated && <Link to={`/publication/${post.id}`} className="link">Lire la suite</Link>}
        {post.kind === "buddy" && (
          <>
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--ink-2)" }}>
              <b style={{ fontWeight: 600 }}>{fmtWhen(post.starts_at)}</b>{post.gym_name ? ` · ${post.gym_name}` : ""}
            </div>
            {!post.mine && (
              <button type="button" className="act" onClick={join} disabled={busy}>
                <span>{busy ? "Envoi…" : "Je viens"}</span><Icon name="send" size={16} stroke={2.2} />
              </button>
            )}
            {error && <p className="error" role="alert">{error}</p>}
          </>
        )}
        <div className="tools"><LikeButton post={post} /></div>
      </div>
    </article>
  );
}

function PromoCard({ f }) {
  useEffect(() => { api.post(`/features/${f.id}/seen/`).catch(() => {}); }, [f.id]);
  return (
    <Link to={f.link} className="promo" onClick={() => api.post(`/features/${f.id}/click/`).catch(() => {})}>
      <span className="tag">{f.label}</span>
      <b>{f.title}</b>
      <span className="small muted">{f.subtitle}</span>
    </Link>
  );
}

// Le fil classé par le serveur : on charge page par page avec le curseur qu'il renvoie.
function useFeed(query, enabled) {
  const [s, setS] = useState({ items: [], next: null, loading: enabled, error: null });
  const gen = useRef(0);
  const load = useCallback(async (cursor) => {
    const id = ++gen.current;
    setS((x) => ({ ...x, items: cursor ? x.items : [], loading: true, error: null }));
    try {
      const qs = new URLSearchParams(query);
      if (cursor) qs.set("cursor", cursor);
      const res = await api.get(`/feed/?${qs}`);
      if (id !== gen.current) return;
      setS((x) => ({ items: cursor ? [...x.items, ...res.results] : res.results, next: res.next, loading: false, error: null }));
      const ids = res.results.filter((r) => r.type === "post" && !r.post.mine).map((r) => r.post.id);
      if (ids.length) api.post("/feed/seen/", { ids }).catch(() => {});
    } catch (error) {
      if (id === gen.current) setS((x) => ({ ...x, loading: false, error }));
    }
  }, [query]);
  useEffect(() => { if (enabled) load(""); }, [load, enabled]);
  const drop = (postId) => setS((x) => ({ ...x, items: x.items.filter((r) => !(r.type === "post" && r.post.id === postId)) }));
  return { ...s, more: () => load(s.next), drop };
}

export default function Fil() {
  const [tab, setTab] = useState(0);
  const feed = useFeed(TABS[tab][0], tab !== MARKET);
  const convs = useFetch("/conversations/");
  const notifs = useFetch("/notifications/");
  const unread = (convs.data || []).some((c) => c.unread > 0);
  const bell = notifs.data?.unread || 0;

  return (
    <main className="page">
      <div className="titlebar">
        <h1 className="h" style={{ fontSize: 32, lineHeight: 1 }}>Fil</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/notifications" className="iconbtn" aria-label={bell ? `Notifications, ${bell} nouvelles` : "Notifications"}>
            <Icon name="bell" size={18} />{bell > 0 && <span className="dot" />}
          </Link>
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
      {tab === MARKET ? <MarcheTab /> : feed.loading && feed.items.length === 0 ? <Loading /> : feed.error && feed.items.length === 0 ? <Empty title="Impossible de charger le fil">{feed.error.message}</Empty> : feed.items.length === 0 ? (
        <Empty title="Rien ici pour l'instant">Sois le premier à publier ou à chercher un binôme.</Empty>
      ) : (
        <>
          {feed.items.map((r) => (r.type === "feature" ? <PromoCard key={`f${r.feature.id}`} f={r.feature} /> : <Entry key={r.post.id} post={r.post} onGone={feed.drop} />))}
          {feed.next && <div style={{ padding: "12px 20px" }}><button type="button" className="btn ghost" disabled={feed.loading} onClick={feed.more}>{feed.loading ? "Chargement…" : "Voir plus"}</button></div>}
        </>
      )}
      <TabBar />
    </main>
  );
}
