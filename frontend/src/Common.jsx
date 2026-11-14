import { Icon } from "./ui";
import { DAY_NAMES, goalLabel, periodLabel } from "./labels";

export function Tick() {
  return <Icon name="check" size={14} stroke={3} color="var(--ok)" />;
}

// Points communs entre moi et un binôme, d'après la réponse de /api/matches/.
export function Reasons({ m }) {
  const r = m.reasons;
  const slot = [r.days.map((d) => DAY_NAMES[d]).join(", "), r.periods.map((p) => periodLabel(p).toLowerCase()).join(", ")].filter(Boolean).join(" · ");
  return (
    <div>
      <div className="cr"><span className="l">Salle</span><span className="v">{r.gym ? <>Même salle <Tick /></> : r.commune ? "Même commune" : m.gym?.name || "—"}</span></div>
      <div className="cr"><span className="l">Objectif</span><span className="v">{r.goals.length ? <>{r.goals.map(goalLabel).join(", ")} <Tick /></> : "Différent"}</span></div>
      <div className="cr"><span className="l">Créneau</span><span className="v">{slot ? <>{slot} <Tick /></> : "Aucun en commun"}</span></div>
      <div className="cr"><span className="l">Niveau</span><span className="v">{r.level ? <>Même niveau <Tick /></> : "Niveau différent"}</span></div>
      <div className="cr"><span className="l">Ponctualité</span><span className="v">{m.punctuality != null ? <>{String(m.punctuality).replace(".", ",")} / 5 <span className="muted" style={{ fontWeight: 400 }}>· {m.sessions_done} séances</span></> : <span className="muted" style={{ fontWeight: 400 }}>Pas encore notée</span>}</span></div>
    </div>
  );
}

export function Score({ value, size = 44 }) {
  return (
    <span className="score" style={{ fontSize: size }} aria-label={`Compatibilité ${value} pour cent`}>
      {value}<span style={{ fontSize: size * 0.32, fontWeight: 700 }}>%</span>
    </span>
  );
}
