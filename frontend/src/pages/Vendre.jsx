import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useAction, useFetch } from "../hooks";
import { shrinkImage } from "../image";
import { CATEGORIES, CONDITIONS } from "../labels";
import { Icon, Toggle } from "../ui";

const MAX_PHOTOS = 4;

export default function Vendre() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { busy, error, run, setError } = useAction();
  const gyms = useFetch(`/gyms/?${new URLSearchParams(user.commune ? { commune: user.commune } : {})}`);
  const fileInput = useRef(null);
  const [photos, setPhotos] = useState([]); // { file, preview }
  const [f, setF] = useState({ title: "", price: "", condition: "very_good", category: "weights", description: "", handover: true, gym: user.profile.gym || "" });
  const [createdId, setCreatedId] = useState(null);
  const set = (p) => setF((x) => ({ ...x, ...p }));

  useEffect(() => () => photos.forEach((p) => URL.revokeObjectURL(p.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps

  const addFiles = (e) => {
    const files = [...e.target.files].filter((x) => x.type.startsWith("image/")).slice(0, MAX_PHOTOS - photos.length);
    setPhotos((p) => [...p, ...files.map((file) => ({ file, preview: URL.createObjectURL(file) }))]);
    e.target.value = "";
  };
  const removePhoto = (i) => setPhotos((p) => { URL.revokeObjectURL(p[i].preview); return p.filter((_, j) => j !== i); });

  const publish = (e) => {
    e.preventDefault();
    run(async () => {
      const listing = await api.post("/listings/", {
        title: f.title.trim(), description: f.description.trim(), price: Number(f.price), category: f.category,
        condition: f.condition, handover_at_gym: f.handover && !!f.gym, gym: f.gym ? Number(f.gym) : null,
      });
      let failed = 0;
      for (const p of photos) {
        const body = new FormData();
        body.append("image", await shrinkImage(p.file));
        try { await api.upload(`/listings/${listing.id}/photos/`, body); } catch { failed += 1; }
      }
      if (failed) {
        setCreatedId(listing.id);
        setError(`Ton annonce est publiée, mais ${failed} photo${failed > 1 ? "s n'ont" : " n'a"} pas pu être envoyée${failed > 1 ? "s" : ""}.`);
        return;
      }
      nav(`/marche/${listing.id}`, { replace: true });
    });
  };

  const valid = f.title.trim().length >= 3 && Number(f.price) >= 500;

  return (
    <main className="page bare">
      <div className="topbar between">
        <button type="button" className="link" style={{ fontSize: 15, textDecoration: "none", color: "var(--ink-2)" }} onClick={() => nav(-1)}>Annuler</button>
        <span className="h" style={{ fontSize: 18, letterSpacing: "-0.02em" }}>Vendre un article</span>
        <span style={{ width: 52 }} />
      </div>

      <form onSubmit={publish} className="pad" style={{ paddingTop: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        <div className="thumbs">
          {photos.length < MAX_PHOTOS && (
            <button type="button" className="addphoto" onClick={() => fileInput.current.click()}>
              <Icon name="plus" size={20} stroke={2} />Photo
            </button>
          )}
          {photos.map((p, i) => (
            <div className="thumb" key={p.preview}>
              <img src={p.preview} alt={`Photo ${i + 1}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              <button type="button" aria-label={`Retirer la photo ${i + 1}`} onClick={() => removePhoto(i)}>×</button>
            </div>
          ))}
          <input ref={fileInput} type="file" accept="image/*" multiple hidden onChange={addFiles} aria-label="Ajouter des photos" />
        </div>
        <span className="hint" style={{ marginTop: -6 }}>Jusqu'à {MAX_PHOTOS} photos. Une bonne photo vend plus vite.</span>

        <div className="field"><label className="k" htmlFor="title">Titre</label><input id="title" className="input" maxLength={80} placeholder="Haltères 2 × 10 kg" value={f.title} onChange={(e) => set({ title: e.target.value })} /></div>
        <div className="field"><label className="k" htmlFor="price">Prix (FCFA)</label><input id="price" className="input" type="number" inputMode="numeric" min="500" step="500" placeholder="18000" value={f.price} onChange={(e) => set({ price: e.target.value })} /></div>
        <div className="field"><span className="k">État</span><div className="chips">{CONDITIONS.map((c) => <button type="button" key={c.code} aria-pressed={f.condition === c.code} className={`chip ${f.condition === c.code ? "on" : ""}`} onClick={() => set({ condition: c.code })}>{c.label}</button>)}</div></div>
        <div className="field"><span className="k">Catégorie</span><div className="chips">{CATEGORIES.map((c) => <button type="button" key={c.code} aria-pressed={f.category === c.code} className={`chip ${f.category === c.code ? "on" : ""}`} onClick={() => set({ category: c.code })}>{c.label}</button>)}</div></div>
        <div className="field"><label className="k" htmlFor="desc">Description</label><textarea id="desc" className="input" rows={3} maxLength={500} placeholder="Utilisés pendant un an, en très bon état." value={f.description} onChange={(e) => set({ description: e.target.value })} /></div>

        <div style={{ borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)", padding: "14px 0", display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ flex: 1, minWidth: 0 }}><div style={{ fontWeight: 600, fontSize: 15 }}>Remise à la salle</div><div className="small muted" style={{ marginTop: 2 }}>Un lieu sûr pour la remise en main propre</div></div>
            <Toggle on={f.handover} onChange={(v) => set({ handover: v })} label="Remise à la salle" />
          </div>
          {f.handover && (
            <select aria-label="Salle de remise" className="input" value={f.gym} onChange={(e) => set({ gym: e.target.value })}>
              <option value="">Choisir une salle</option>
              {(gyms.data || []).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          )}
        </div>

        {error && <p className="error" role="alert">{error}</p>}
        {createdId && <Link to={`/marche/${createdId}`} className="btn ghost">Voir mon annonce</Link>}
        {!createdId && <button className="btn" disabled={!valid || busy} style={{ marginBottom: 28 }}>{busy ? "Publication…" : "Publier l'article"}</button>}
      </form>
    </main>
  );
}
