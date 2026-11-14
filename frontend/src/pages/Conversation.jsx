import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { Avatar, BackButton, Icon, Verified } from "../ui";

const QUICK = ["Je suis en route", "5 min de retard", "Je suis arrivé"];
const POLL_MS = 4000;

export default function Conversation() {
  const { id } = useParams();
  const convs = useFetch("/conversations/");
  const other = convs.data?.find((c) => String(c.id) === id)?.other;
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const { busy, error, run } = useAction();
  const last = useRef(0);
  const end = useRef(null);

  const pull = useCallback(async () => {
    try {
      const fresh = await api.get(`/conversations/${id}/messages/?after=${last.current}`);
      if (fresh.length) {
        last.current = fresh[fresh.length - 1].id;
        setMessages((prev) => [...prev, ...fresh.filter((m) => !prev.some((p) => p.id === m.id))]);
      }
    } catch { /* le prochain passage réessaiera */ }
  }, [id]);

  useEffect(() => {
    last.current = 0;
    setMessages([]);
    pull();
    const t = setInterval(pull, POLL_MS);
    return () => clearInterval(t);
  }, [pull]);

  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [messages.length]);

  const send = (body) =>
    run(async () => {
      const msg = await api.post(`/conversations/${id}/messages/`, { body });
      last.current = Math.max(last.current, msg.id);
      setMessages((prev) => [...prev, msg]);
      setText("");
    });

  const submit = (e) => { e.preventDefault(); if (text.trim()) send(text.trim()); };

  return (
    <main className="page bare" style={{ height: "100dvh" }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, padding: "28px 24px 12px", background: "var(--surface)", borderBottom: "1px solid var(--line)" }}>
        <BackButton to="/messages" />
        {other && (
          <Link to={`/membres/${other.id}`} style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <Avatar person={other} size={42} />
            <div style={{ fontWeight: 700, fontSize: 16, display: "flex", alignItems: "center", gap: 6 }}>{other.display_name}{other.pro_verified && <Verified />}</div>
          </Link>
        )}
      </header>

      <div className="bubbles" aria-live="polite">
        {messages.length === 0 && <p className="hint" style={{ textAlign: "center", marginTop: 24 }}>Dis bonjour pour lancer la discussion.</p>}
        {messages.map((m) => <div key={m.id} className={`bub ${m.mine ? "me" : "you"}`}>{m.body}</div>)}
        <div ref={end} />
      </div>

      <div style={{ display: "flex", gap: 8, padding: "6px 24px 0", overflowX: "auto" }}>
        {QUICK.map((q) => <button key={q} type="button" className="chip" style={{ height: 36, fontSize: 13.5, flex: "none" }} disabled={busy} onClick={() => send(q)}>{q}</button>)}
      </div>
      {error && <p className="error pad" role="alert">{error}</p>}
      <form className="composer" onSubmit={submit}>
        <input aria-label="Ton message" placeholder="Écris un message" value={text} maxLength={1000} onChange={(e) => setText(e.target.value)} />
        <button className="send" aria-label="Envoyer" disabled={busy || !text.trim()}><Icon name="send" size={18} stroke={2.4} /></button>
      </form>
    </main>
  );
}
