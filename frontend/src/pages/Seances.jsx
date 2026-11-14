import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { BookingRow } from "../Bookings";
import { useAction, useFetch } from "../hooks";
import { dayParts, fmtTime } from "../labels";
import { Empty, Loading, TabBar } from "../ui";
import { useStartChat } from "./Binomes";

const STATUS = {
  pending: ["En attente de réponse", "var(--accent-ink)"],
  confirmed: ["Confirmée", "var(--ok)"],
  done: ["Terminée", "var(--mute)"],
  cancelled: ["Annulée", "var(--mute)"],
};

function Meetup({ m, onChange }) {
  const { busy, error, run } = useAction();
  const chat = useStartChat();
  const other = m.mine ? m.organizer : m.partner;
  const { day, weekday } = dayParts(m.starts_at);
  const [label, color] = STATUS[m.status];
  const act = (action, body) => run(async () => { await api.post(`/meetups/${m.id}/${action}/`, body); await onChange(); });

  return (
    <div className="se" style={{ alignItems: "flex-start" }}>
      <div className="dt"><div className="dd">{day}</div><div className="dw">{weekday}</div></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{fmtTime(m.starts_at)} · {m.focus || "Séance à deux"}</div>
        <div style={{ fontSize: 13.5, color: "#55554f", marginTop: 3 }}>{m.gym_name ? `${m.gym_name} · ` : ""}avec {other.display_name}</div>
        <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 6, color }}>{m.status === "pending" && !m.mine ? "En attente de sa réponse" : label}</div>

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {m.status === "pending" && m.mine && (
            <>
              <button type="button" className="btn sm" disabled={busy} onClick={() => act("respond", { accept: true })}>Accepter</button>
              <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("respond", { accept: false })}>Refuser</button>
            </>
          )}
          {m.status === "confirmed" && (
            <button type="button" className="btn sm" disabled={busy} onClick={() => act("arrive")}>Je suis arrivé</button>
          )}
          {["pending", "confirmed"].includes(m.status) && (
            <>
              <button type="button" className="btn ghost sm" disabled={chat.busy} onClick={() => chat.start(other.id)}>Écrire</button>
              {!(m.status === "pending" && m.mine) && <button type="button" className="link" disabled={busy} onClick={() => act("cancel")}>Annuler</button>}
            </>
          )}
        </div>
        {(error || chat.error) && <p className="error" role="alert" style={{ marginTop: 8 }}>{error || chat.error}</p>}
      </div>
    </div>
  );
}

export default function Seances() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") === "bookings" ? "bookings" : "upcoming");
  const { data, loading, error, reload } = useFetch(tab === "bookings" ? "/bookings/?when=upcoming" : `/meetups/?when=${tab}`);

  return (
    <main className="page">
      <div className="titlebar"><h1 className="h" style={{ fontSize: 32, lineHeight: 1 }}>Séances</h1></div>
      <div className="tabs" role="tablist">
        {[["upcoming", "À venir"], ["bookings", "Réservations"], ["past", "Passées"]].map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      {loading ? <Loading /> : error ? <Empty title="Impossible de charger tes séances">{error.message}</Empty> : data.length === 0 ? (
        tab === "bookings" ? (
          <Empty title="Aucune réservation">
            Réserve une séance avec un coach ou un pro.
            <div style={{ marginTop: 16 }}><Link to="/pros" className="btn ghost sm">Voir les pros</Link></div>
          </Empty>
        ) : (
          <Empty title={tab === "upcoming" ? "Aucune séance prévue" : "Aucune séance passée"}>
            {tab === "upcoming" ? "Trouve un binôme et propose-lui une séance." : "Tes séances terminées apparaîtront ici."}
          </Empty>
        )
      ) : tab === "bookings" ? data.map((b) => <BookingRow key={b.id} b={b} onChange={reload} />) : data.map((m) => <Meetup key={m.id} m={m} onChange={reload} />)}
      <TabBar />
    </main>
  );
}
