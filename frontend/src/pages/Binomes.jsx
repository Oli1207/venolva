import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Reasons, Score } from "../Common";
import { useAction, useFetch } from "../hooks";
import { goalLabel, levelLabel } from "../labels";
import { Avatar, Empty, Loading, TabBar } from "../ui";

export function useStartChat() {
  const nav = useNavigate();
  const { busy, error, run } = useAction();
  const start = (userId) => run(async () => {
    const conv = await api.post("/conversations/start/", { user: userId });
    nav(`/messages/${conv.id}`);
  });
  return { start, busy, error };
}

export default function Binomes() {
  const [params] = useSearchParams();
  const gymFilter = params.get("gym");
  const [wide, setWide] = useState(false);
  const { data, loading, error } = useFetch(`/matches/?min=${wide || gymFilter ? 0 : 40}${gymFilter ? `&gym=${gymFilter}` : ""}`);
  const chat = useStartChat();
  const [first, ...rest] = data || [];

  return (
    <main className="page">
      <div className="titlebar">
        <div>
          <div className="k">{gymFilter ? "Dans cette salle" : "Pour toi"}</div>
          <h1 className="h" style={{ fontSize: 32, lineHeight: 1, marginTop: 6 }}>Binômes</h1>
        </div>
      </div>

      {loading ? <Loading /> : error ? <Empty title="Impossible de charger les binômes">{error.message}</Empty> : !first ? (
        <Empty title="Pas encore de binôme">
          Personne ne correspond pour l'instant.
          {!wide && <div style={{ marginTop: 16 }}><button type="button" className="btn ghost sm" onClick={() => setWide(true)}>Élargir la recherche</button></div>}
        </Empty>
      ) : (
        <>
          <div className="pad">
            <div className="panel">
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <Avatar person={first} size={64} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="h" style={{ fontSize: 22, letterSpacing: "-0.03em", lineHeight: 1.1 }}>{first.display_name}{first.age ? `, ${first.age}` : ""}</div>
                  <div className="small muted" style={{ marginTop: 4 }}>{first.goals.map(goalLabel).join(", ")} · {levelLabel(first.level)}</div>
                </div>
                <Score value={first.score} />
              </div>
              <div style={{ marginTop: 14, borderTop: "1px solid var(--line-2)" }}><Reasons m={first} /></div>
              {first.bio && <p style={{ margin: "8px 0 0", fontSize: 14, lineHeight: 1.5, color: "var(--ink-2)" }}>« {first.bio} »</p>}
              <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
                <button type="button" className="btn sm" style={{ flex: 1 }} disabled={chat.busy} onClick={() => chat.start(first.id)}>Dire bonjour</button>
                <Link to={`/membres/${first.id}`} className="btn ghost sm" style={{ width: "auto" }}>Profil</Link>
              </div>
              {chat.error && <p className="error" role="alert">{chat.error}</p>}
            </div>
          </div>
          <div className="rows" style={{ paddingTop: 8 }}>
            {rest.map((m) => (
              <Link key={m.id} to={`/membres/${m.id}`} className="row" style={{ height: 72 }}>
                <Avatar person={m} size={44} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>{m.display_name}{m.age ? `, ${m.age}` : ""}</div>
                  <div className="small muted" style={{ marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{m.goals.map(goalLabel).join(", ")}{m.gym ? ` · ${m.gym.name}` : ""}</div>
                </div>
                <Score value={m.score} size={24} />
              </Link>
            ))}
          </div>
        </>
      )}
      <TabBar />
    </main>
  );
}
