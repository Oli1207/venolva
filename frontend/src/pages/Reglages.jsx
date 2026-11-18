import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { BackButton, Loading } from "../ui";

export default function Reglages() {
  const { logout } = useAuth();
  const blocks = useFetch("/blocks/");
  const unblock = useAction();
  const del = useAction();
  const [confirm, setConfirm] = useState("");
  const [open, setOpen] = useState(false);

  const remove = () =>
    del.run(async () => {
      await api.del("/auth/me/", { confirm });
      logout();
    });

  return (
    <main className="page bare">
      <div className="topbar"><BackButton to="/profil" /></div>
      <h1 className="h pad" style={{ fontSize: 30, margin: "6px 0 10px" }}>Réglages</h1>

      <div className="rows">
        <div className="k">Membres bloqués</div>
        {blocks.loading ? <Loading /> : blocks.data.length === 0 ? <p className="hint">Tu n'as bloqué personne.</p> : blocks.data.map((b) => (
          <div key={b.id} className="row" style={{ cursor: "default" }}>
            <span style={{ flex: 1 }}>{b.display_name || "Membre"}</span>
            <button type="button" className="btn ghost sm" disabled={unblock.busy} onClick={() => unblock.run(async () => { await api.del(`/blocks/${b.id}/`); await blocks.reload(); })}>Débloquer</button>
          </div>
        ))}
        {unblock.error && <p className="error" role="alert">{unblock.error}</p>}
      </div>

      <div className="rows" style={{ paddingTop: 24 }}>
        <div className="k">Supprimer mon compte</div>
        <p className="hint" style={{ margin: "4px 0 10px" }}>Tes publications, annonces et notifications sont effacées, ton profil disparaît. Les paiements passés restent enregistrés sans ton nom. C'est définitif.</p>
        {!open ? (
          <button type="button" className="btn ghost" style={{ color: "#b3261e" }} onClick={() => setOpen(true)}>Supprimer mon compte</button>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <label className="k" htmlFor="confirm">Écris SUPPRIMER pour confirmer</label>
            <input id="confirm" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
            {del.error && <p className="error" role="alert">{del.error}</p>}
            <button type="button" className="btn" style={{ background: "#b3261e" }} disabled={confirm !== "SUPPRIMER" || del.busy} onClick={remove}>{del.busy ? "Suppression…" : "Supprimer définitivement"}</button>
          </div>
        )}
      </div>
    </main>
  );
}
