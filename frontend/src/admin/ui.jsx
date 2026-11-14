import { useState } from "react";
import { useFetch } from "../hooks";

export function Badge({ tone = "", children }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export const PAYMENT_STATUS = {
  pending: ["En attente", ""],
  paid: ["Payé", "ok"],
  failed: ["Échoué", "bad"],
  expired: ["Remplacé", ""],
  review: ["À vérifier", "warn"],
  duplicate: ["Doublon", "warn"],
  refund_due: ["À rembourser", "warn"],
  refunded: ["Remboursé", ""],
};
export const PURPOSE = { booking: "Réservation", class: "Cours" };
export const METHODS = { wave: "Wave", orange: "Orange Money", mtn: "MTN MoMo", moov: "Moov", djamo: "Djamo", card: "Carte", mobile: "Mobile money" };

// Liste paginée par le serveur (25 lignes). Les filtres vivent dans `params`.
export function usePaged(path, params = {}) {
  const [page, setPage] = useState(1);
  const qs = new URLSearchParams({ ...Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null)), page }).toString();
  const res = useFetch(`${path}?${qs}`);
  return { ...res, page, setPage, pages: res.data ? Math.max(1, Math.ceil(res.data.count / 25)) : 1 };
}

export function Pager({ page, pages, setPage, count }) {
  if (pages <= 1) return count != null ? <div className="pager">{count} résultat{count > 1 ? "s" : ""}</div> : null;
  return (
    <div className="pager">
      <span>{count} résultats</span>
      <button type="button" className="btn ghost sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</button>
      <span>Page {page} / {pages}</span>
      <button type="button" className="btn ghost sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Suivant</button>
    </div>
  );
}

export function Page({ title, sub, children }) {
  return (
    <>
      <h1 className="adm-h1">{title}</h1>
      {sub && <p className="adm-sub">{sub}</p>}
      {children}
    </>
  );
}

export function EmptyRow({ cols, children }) {
  return <tr><td colSpan={cols} style={{ textAlign: "center", color: "var(--mute)", padding: 28 }}>{children}</td></tr>;
}
