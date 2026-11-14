import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { fmtPrice } from "../labels";
import { Loading } from "../ui";

const MAX_TRIES = 6; // le webhook peut arriver quelques secondes après le retour du client
const WAIT_MS = 4000;

const MESSAGES = {
  paid: ["Paiement reçu", "Merci. Ta réservation est payée.", "var(--ok)"],
  review: ["Paiement à vérifier", "Nous avons reçu un montant inattendu. L'équipe vérifie et te contacte si besoin.", "var(--accent-ink)"],
  duplicate: ["Déjà payé", "Tu avais déjà payé cette part. Le second paiement sera remboursé.", "var(--accent-ink)"],
  failed: ["Paiement refusé", "Rien n'a été débité. Tu peux réessayer ou payer sur place.", "#b00020"],
  expired: ["Paiement remplacé", "Une tentative plus récente existe pour cette réservation.", "var(--mute)"],
};

export default function PaiementRetour() {
  const [params] = useSearchParams();
  const ref = params.get("ref");
  const [payment, setPayment] = useState(null);
  const [error, setError] = useState("");
  const tries = useRef(0);

  useEffect(() => {
    if (!ref) return undefined;
    let alive = true;
    let timer;
    const check = async () => {
      try {
        const p = await api.post(`/payments/${encodeURIComponent(ref)}/verify/`);
        if (!alive) return;
        setPayment(p);
        tries.current += 1;
        if (p.status === "pending" && tries.current < MAX_TRIES) timer = setTimeout(check, WAIT_MS);
      } catch (e) {
        if (alive) setError(e.message);
      }
    };
    check();
    return () => { alive = false; clearTimeout(timer); };
  }, [ref]);

  const done = payment && payment.status !== "pending";
  const waiting = payment?.status === "pending" && tries.current < MAX_TRIES;
  const msg = payment && MESSAGES[payment.status];
  const back = payment?.purpose === "class" ? "/fil" : "/seances?tab=bookings";

  return (
    <main className="page bare">
      <div className="pad" style={{ paddingTop: 72, display: "flex", flexDirection: "column", gap: 16 }}>
        {!ref || error ? (
          <>
            <h1 className="h" style={{ fontSize: 32, lineHeight: 1.05 }}>Paiement introuvable</h1>
            <p style={{ margin: 0, color: "#55554f" }}>{error || "Il manque la référence du paiement."}</p>
          </>
        ) : !payment ? <Loading text="Vérification de ton paiement…" /> : waiting ? (
          <>
            <h1 className="h" style={{ fontSize: 32, lineHeight: 1.05 }}>On attend la confirmation</h1>
            <p style={{ margin: 0, color: "#55554f", lineHeight: 1.5 }}>Si tu viens de payer, cela prend quelques secondes. Cette page se met à jour toute seule.</p>
            <Loading text="Vérification en cours…" />
          </>
        ) : msg ? (
          <>
            <h1 className="h" style={{ fontSize: 34, lineHeight: 1.05, color: msg[2] }}>{msg[0]}</h1>
            <p style={{ margin: 0, color: "#55554f", lineHeight: 1.5 }}>{msg[1]}</p>
            <div className="cr" style={{ marginTop: 8 }}><span className="l">Montant</span><span className="v">{fmtPrice(payment.amount)}</span></div>
            <div className="cr"><span className="l">Référence</span><span className="v small" style={{ wordBreak: "break-all" }}>{payment.reference}</span></div>
          </>
        ) : (
          <>
            <h1 className="h" style={{ fontSize: 32, lineHeight: 1.05 }}>Paiement non confirmé</h1>
            <p style={{ margin: 0, color: "#55554f", lineHeight: 1.5 }}>Nous n'avons pas encore reçu la confirmation. Si tu as été débité, elle arrivera dans quelques minutes : la réservation se mettra à jour toute seule.</p>
          </>
        )}
        {(done || (payment && !waiting) || error) && <Link to={back} className="btn" style={{ marginTop: 12 }}>Voir mes réservations</Link>}
      </div>
    </main>
  );
}
