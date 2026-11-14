import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Reasons, Score } from "../Common";
import { useAction, useFetch } from "../hooks";
import { defaultLocalInput, goalLabel, levelLabel, localToIso } from "../labels";
import { Avatar, BackButton, Empty, Loading } from "./../ui";
import { useStartChat } from "./Binomes";

export default function Membre() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const { data: m, loading, error } = useFetch(`/members/${id}/`);
  const chat = useStartChat();
  const propose = useAction();
  const [open, setOpen] = useState(false);
  const [when, setWhen] = useState(defaultLocalInput(24));
  const [focus, setFocus] = useState("");

  const submit = (e) => {
    e.preventDefault();
    propose.run(async () => {
      await api.post("/meetups/", { partner: m.id, starts_at: localToIso(when), gym: m.gym?.id ?? user.profile.gym ?? null, focus });
      const conv = await api.post("/conversations/start/", { user: m.id });
      nav(`/messages/${conv.id}`);
    });
  };

  return (
    <main className="page bare">
      <div className="topbar"><BackButton /></div>
      {loading ? <Loading /> : error ? <Empty title="Profil introuvable">{error.message}</Empty> : (
        <>
          <div className="pad" style={{ paddingTop: 14, display: "flex", alignItems: "center", gap: 16 }}>
            <Avatar person={m} size={84} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="h" style={{ fontSize: 28, lineHeight: 1.1 }}>{m.display_name}{m.age ? `, ${m.age}` : ""}</div>
              <div style={{ fontSize: 14, color: "#55554f", marginTop: 4 }}>{m.goals.map(goalLabel).join(", ")} · {levelLabel(m.level)}</div>
              <div className="small muted" style={{ marginTop: 2 }}>{m.commune}{m.gym ? ` · ${m.gym.name}` : ""}</div>
            </div>
            <Score value={m.score} />
          </div>
          {m.bio && <p className="pad" style={{ margin: "18px 0 0", fontSize: 15, lineHeight: 1.5, color: "var(--ink-2)" }}>« {m.bio} »</p>}
          <div className="pad" style={{ paddingTop: 16 }}>
            <div className="k" style={{ marginBottom: 2 }}>Ce que vous avez en commun</div>
            <Reasons m={m} />
          </div>

          <div className="pad" style={{ marginTop: "auto", paddingTop: 20, paddingBottom: 24, display: "flex", flexDirection: "column", gap: 10 }}>
            {open && (
              <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 6 }}>
                <div className="field"><label className="k" htmlFor="when">Quand</label><input id="when" className="input" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></div>
                <div className="field"><label className="k" htmlFor="focus">Au programme</label><input id="focus" className="input" placeholder="Jambes et fessiers" maxLength={80} value={focus} onChange={(e) => setFocus(e.target.value)} /></div>
                {propose.error && <p className="error" role="alert">{propose.error}</p>}
                <button className="btn" disabled={propose.busy}>{propose.busy ? "Envoi…" : "Envoyer la proposition"}</button>
              </form>
            )}
            {!open && <button type="button" className="btn" disabled={chat.busy} onClick={() => chat.start(m.id)}>Dire bonjour</button>}
            {!open && <button type="button" className="btn ghost" style={{ height: 50, fontSize: 15 }} onClick={() => setOpen(true)}>Proposer une séance</button>}
            {chat.error && <p className="error" role="alert">{chat.error}</p>}
          </div>
        </>
      )}
    </main>
  );
}
