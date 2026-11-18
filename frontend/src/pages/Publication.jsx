import { Link, useNavigate, useParams } from "react-router-dom";
import { useFetch } from "../hooks";
import { PRO_LABELS, ago } from "../labels";
import { Avatar, BackButton, Empty, Loading, Verified } from "../ui";
import { LikeButton, PostMenu } from "./Fil";

// Lecture d'une publication ou d'un article en entier.
export default function Publication() {
  const { id } = useParams();
  const nav = useNavigate();
  const { data: p, loading, error } = useFetch(`/posts/${id}/`);
  return (
    <main className="page bare">
      <div className="topbar between"><BackButton />{p && <PostMenu post={p} onGone={() => nav("/fil", { replace: true })} />}</div>
      {loading ? <Loading /> : error ? <Empty title="Publication introuvable">{error.message}</Empty> : (
        <article className="pad" style={{ paddingTop: 10, paddingBottom: 30 }}>
          {p.kind === "article" && <span className="tag">Article</span>}
          {p.title && <h1 className="h" style={{ fontSize: 28, lineHeight: 1.15, margin: "6px 0 14px" }}>{p.title}</h1>}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
            <Avatar person={p.author} size={38} />
            <div style={{ fontSize: 14 }}>
              <b>{p.author.pro_verified ? <Link to={`/pros/${p.author.id}`}>{p.author.display_name}</Link> : p.author.display_name || "Membre"}</b>
              {p.author.pro_verified && p.author.pro_type && <> <Verified /></>}
              <div className="small muted">{PRO_LABELS[p.author.pro_type] || p.author.commune} · {ago(p.created_at)}</div>
            </div>
          </div>
          {p.body.split("\n").map((line, i) => (line.trim() ? <p key={i} style={{ fontSize: 16.5, lineHeight: 1.6, margin: "0 0 14px" }}>{line}</p> : null))}
          <div className="entry" style={{ padding: 0, border: 0 }}><div className="tools"><LikeButton post={p} /></div></div>
          {p.mine && p.kind === "article" && <Link to="/a-la-une" className="btn ghost" style={{ marginTop: 18, display: "block", textAlign: "center", lineHeight: "48px", height: 48 }}>Demander la mise à la une</Link>}
        </article>
      )}
    </main>
  );
}
