import { useState } from "react";
import { api } from "./api";
import { useAction } from "./hooks";

export const REASONS = [
  ["harassment", "Harcèlement ou comportement déplacé"],
  ["scam", "Arnaque"],
  ["inappropriate", "Contenu inapproprié"],
  ["fake", "Faux profil"],
  ["other", "Autre"],
];

// Feuille du bas : un menu d'options (signaler, bloquer, supprimer…).
export function Sheet({ title, onClose, children }) {
  return (
    <div className="sheet-back" onClick={onClose} role="presentation">
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title || "Options"} onClick={(e) => e.stopPropagation()}>
        {title && <div className="k">{title}</div>}
        {children}
        <button type="button" className="btn ghost" style={{ height: 48 }} onClick={onClose}>Fermer</button>
      </div>
    </div>
  );
}

// Signaler un membre ou une publication : choisir un motif, ajouter un mot si on veut.
export function ReportSheet({ kind, target, onClose }) {
  const [reason, setReason] = useState("");
  const [detail, setDetail] = useState("");
  const [done, setDone] = useState("");
  const { busy, error, run } = useAction();
  const send = () => run(async () => { const r = await api.post("/content-reports/", { kind, target, reason, detail }); setDone(r.detail); });
  return (
    <Sheet title="Signaler" onClose={onClose}>
      {done ? <p style={{ margin: "6px 0" }}>{done}</p> : (
        <>
          {REASONS.map(([code, label]) => (
            <button key={code} type="button" className="opt" aria-pressed={reason === code} style={{ fontWeight: reason === code ? 700 : 400 }} onClick={() => setReason(code)}>{reason === code ? "✓ " : ""}{label}</button>
          ))}
          <textarea className="input" rows={2} maxLength={300} placeholder="Un détail utile (facultatif)" value={detail} onChange={(e) => setDetail(e.target.value)} aria-label="Détail du signalement" />
          {error && <p className="error" role="alert">{error}</p>}
          <button type="button" className="btn" disabled={!reason || busy} onClick={send}>{busy ? "Envoi…" : "Envoyer le signalement"}</button>
        </>
      )}
    </Sheet>
  );
}

export async function blockMember(id) {
  await api.post("/blocks/", { user: id });
}
