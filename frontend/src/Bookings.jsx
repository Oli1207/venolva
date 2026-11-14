import { api } from "./api";
import { useAction } from "./hooks";
import { PayButton } from "./Pay";
import { dayParts, fmtPrice, fmtTime } from "./labels";
import { useStartChat } from "./pages/Binomes";

const STATUS = {
  pending: ["En attente de confirmation", "var(--accent-ink)"],
  confirmed: ["Confirmée", "var(--ok)"],
  declined: ["Refusée", "var(--mute)"],
  cancelled: ["Annulée", "var(--mute)"],
  done: ["Terminée", "var(--mute)"],
};

// Une réservation, vue par le client (ou son binôme) ou par le pro. Les actions dépendent du rôle.
export function BookingRow({ b, onChange }) {
  const { busy, error, run } = useAction();
  const chat = useStartChat();
  const isPro = b.role === "pro";
  const { day, weekday } = dayParts(b.starts_at);
  const [label, color] = STATUS[b.status];
  const who = isPro
    ? `${b.client.display_name}${b.partner ? ` et ${b.partner.display_name}` : ""}`
    : b.role === "partner" ? `${b.pro.display_name}, invité par ${b.client.display_name}` : b.pro.display_name;
  const amount = isPro ? b.price_total : b.price_client;
  const live = ["pending", "confirmed"].includes(b.status);
  const act = (action) => run(async () => { await api.post(`/bookings/${b.id}/${action}/`); await onChange(); });
  const startsPassed = new Date(b.starts_at) <= new Date();
  // Le paiement en ligne s'ouvre quand le pro a confirmé (sinon il faudrait rembourser en cas de refus).
  const canPay = !isPro && b.status === "confirmed" && b.payment_status !== "paid" && !b.paid_by_me && b.my_share > 0;

  return (
    <div className="se" style={{ alignItems: "flex-start" }}>
      <div className="dt"><div className="dd">{day}</div><div className="dw">{weekday}</div></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{fmtTime(b.starts_at)} · {b.service.name}</div>
        <div style={{ fontSize: 13.5, color: "#55554f", marginTop: 3 }}>{b.gym_name ? `${b.gym_name} · ` : ""}{isPro ? "avec" : "chez"} {who}</div>
        <div style={{ fontSize: 12.5, marginTop: 6, display: "flex", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 600, color }}>{label}</span>
          <span className="muted">{fmtPrice(amount)} · {b.payment_status === "paid" ? <span className="tag-ok">Payée</span> : b.payment_status === "partial" ? "Partiellement payée" : b.paid_by_me ? <span className="tag-ok">Ta part est payée</span> : "À payer"}</span>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {isPro && b.status === "pending" && (
            <>
              <button type="button" className="btn sm" disabled={busy} onClick={() => act("confirm")}>Confirmer</button>
              <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("decline")}>Refuser</button>
            </>
          )}
          {isPro && b.status === "confirmed" && startsPassed && <button type="button" className="btn sm" disabled={busy} onClick={() => act("complete")}>Séance terminée</button>}
          {isPro && b.payment_status === "unpaid" && live && b.status === "confirmed" && <button type="button" className="btn ghost sm" disabled={busy} onClick={() => act("mark_paid")}>Marquer payée</button>}
          {live && <button type="button" className="btn ghost sm" disabled={chat.busy} onClick={() => chat.start(isPro ? b.client.id : b.pro.id)}>Écrire</button>}
          {live && b.role !== "partner" && <button type="button" className="link" disabled={busy} onClick={() => act("cancel")}>Annuler</button>}
        </div>
        {canPay && <div style={{ marginTop: 12 }}><PayButton purpose="booking" target={b.id} amount={b.my_share} /><p className="hint" style={{ margin: "6px 0 0" }}>Ou paie sur place, directement au professionnel.</p></div>}
        {(error || chat.error) && <p className="error" role="alert" style={{ marginTop: 8 }}>{error || chat.error}</p>}
      </div>
    </div>
  );
}
