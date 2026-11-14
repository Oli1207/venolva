import { useState } from "react";
import { api } from "./api";
import { useAction, useFetch } from "./hooks";
import { fmtPrice } from "./labels";
import { Loading, Radio } from "./ui";

// Panneau de choix du moyen de paiement. Envoie ensuite vers la page sécurisée du prestataire (Jeko ou Paystack).
export function PayBox({ purpose, target, amount, onCancel }) {
  const methods = useFetch("/payments/methods/");
  const { busy, error, run } = useAction();
  const [method, setMethod] = useState("");

  const go = () =>
    run(async () => {
      const p = await api.post("/payments/", { purpose, target, method });
      // On ne suit que des adresses sécurisées renvoyées par notre serveur.
      if (!/^https:\/\//.test(p.checkout_url)) throw new Error("Adresse de paiement invalide.");
      window.location.assign(p.checkout_url);
    });

  return (
    <div style={{ marginTop: 12, padding: 14, borderRadius: 14, background: "var(--surface)", border: "1px solid var(--line-2)" }}>
      <div className="k" style={{ marginBottom: 4 }}>Payer {fmtPrice(amount)} avec</div>
      {methods.loading ? <Loading /> : !methods.data?.length ? (
        <p className="hint" style={{ margin: "8px 0" }}>Le paiement en ligne n'est pas disponible pour le moment. Tu peux payer sur place.</p>
      ) : (
        methods.data.map((m) => (
          <button key={m.code} type="button" className="row" style={{ minHeight: 48 }} aria-pressed={method === m.code} onClick={() => setMethod(m.code)}>
            <span style={{ fontSize: 15, fontWeight: method === m.code ? 700 : 500 }}>{m.label}</span>
            <Radio on={method === m.code} />
          </button>
        ))
      )}
      {error && <p className="error" role="alert" style={{ marginTop: 8 }}>{error}</p>}
      <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center" }}>
        <button type="button" className="btn sm" disabled={!method || busy} onClick={go}>{busy ? "Ouverture…" : "Continuer vers le paiement"}</button>
        <button type="button" className="link" onClick={onCancel}>Annuler</button>
      </div>
      <p className="hint" style={{ margin: "10px 0 0" }}>Tu quittes Djinzin pour une page de paiement sécurisée. Nous ne voyons ni ton code secret ni ta carte.</p>
    </div>
  );
}

export function PayButton({ purpose, target, amount, label }) {
  const [open, setOpen] = useState(false);
  return open ? (
    <PayBox purpose={purpose} target={target} amount={amount} onCancel={() => setOpen(false)} />
  ) : (
    <button type="button" className="btn sm" onClick={() => setOpen(true)}>{label || `Payer ${fmtPrice(amount)}`}</button>
  );
}
