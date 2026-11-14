import { NavLink, useNavigate } from "react-router-dom";

const PATHS = {
  back: "M15 5l-7 7 7 7",
  plus: "M12 5v14M5 12h14",
  chevron: "M9 5l7 7-7 7",
  check: "M5 12.5l4.5 4.5L19 7.5",
  send: "M5 12h14M13 6l6 6-6 6",
  search: "M20 20l-4-4M11 18a7 7 0 1 1 0-14 7 7 0 0 1 0 14z",
  feed: "M4 6h16M4 12h16M4 18h10",
  users: "M2.5 20c.5-4 3-6 6.5-6s6 2 6.5 6M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.3c2 .8 3.3 2.7 3.5 5.700M12.500 8a3.500 3.500 0 1 1-7 0 3.500 3.500 0 0 1 7 0z",
  calendar: "M4 10h16M9 3v4M15 3v4M7 5h10a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V8a3 3 0 0 1 3-3z",
  user: "M4 21c.7-4.5 4-7 8-7s7.3 2.5 8 7M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0z",
  chat: "M20 12a8 8 0 0 1-11.5 7.2L4 20l1-4.3A8 8 0 1 1 20 12z",
  pin: "M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21zM14.5 9.500a2.500 2.500 0 1 1-5 0 2.500 2.500 0 0 1 5 0z",
};

export function Icon({ name, size = 22, stroke = 1.8, color }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color || "currentColor"} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

const TINTS = ["t0", "t1", "t2", "t3"];
export function Avatar({ person, size = 44 }) {
  const tint = TINTS[(person?.id ?? 0) % TINTS.length];
  return (
    <div className={`av ${tint}`} style={{ width: size, height: size, fontSize: Math.round(size * 0.34) }} aria-hidden="true">
      {person?.initials || "?"}
    </div>
  );
}

const STAR = "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z";

// Étoiles de notation : lecture seule, ou cliquables si onChange est fourni.
export function Stars({ value = 0, onChange, size = 20 }) {
  return (
    <span style={{ display: "inline-flex", gap: 2 }} role={onChange ? "radiogroup" : "img"} aria-label={`Note : ${value} sur 5`}>
      {[1, 2, 3, 4, 5].map((n) => {
        const star = (
          <svg width={size} height={size} viewBox="0 0 24 24" fill={n <= Math.round(value) ? "var(--accent)" : "none"} stroke={n <= Math.round(value) ? "var(--accent)" : "#b9b9b2"} strokeWidth="1.6" strokeLinejoin="round" aria-hidden="true"><path d={STAR} /></svg>
        );
        return onChange ? (
          <button key={n} type="button" role="radio" aria-checked={n === value} aria-label={`${n} sur 5`} onClick={() => onChange(n)} style={{ background: "none", border: 0, padding: 2, cursor: "pointer" }}>{star}</button>
        ) : <span key={n}>{star}</span>;
      })}
    </span>
  );
}

export function Verified({ size = 13 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label="Compte vérifié">
      <circle cx="12" cy="12" r="12" fill="#0B7A47" />
      <path d="M7 12.5l3.5 3.5L17 9" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Radio({ on }) {
  return <span className={`rd ${on ? "on" : ""}`}>{on && <Icon name="check" size={12} stroke={3.5} />}</span>;
}

export function Toggle({ on, onChange, label }) {
  return <button type="button" role="switch" aria-checked={on} aria-label={label} className={`toggle ${on ? "on" : ""}`} onClick={() => onChange(!on)} />;
}

export function BackButton({ to }) {
  const nav = useNavigate();
  return (
    <button type="button" className="back" aria-label="Retour" onClick={() => (to ? nav(to) : nav(-1))}>
      <Icon name="back" />
    </button>
  );
}

export function Wordmark({ size = 24 }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <svg width={size + 4} height={size + 4} viewBox="0 0 32 32" fill="none" aria-hidden="true">
        <circle cx="12" cy="20" r="8" stroke="#0D0D0D" strokeWidth="4.5" />
        <path d="M24 3v26" stroke="#FF6A13" strokeWidth="4.5" />
      </svg>
      <span className="h" style={{ fontSize: size }}>djinzin</span>
    </div>
  );
}

export function TabBar() {
  const items = [
    ["/fil", "feed", "Fil"],
    ["/binomes", "users", "Binômes"],
    ["/seances", "calendar", "Séances"],
    ["/profil", "user", "Profil"],
  ];
  return (
    <nav className="nav" aria-label="Navigation principale">
      {items.map(([to, icon, label]) => (
        <NavLink key={to} to={to} className={({ isActive }) => `ni ${isActive ? "on" : ""}`}>
          <Icon name={icon} size={24} />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export function Loading({ text = "Chargement…" }) {
  return <div className="loading" role="status">{text}</div>;
}

export function Empty({ title, children }) {
  return (
    <div className="empty">
      <b>{title}</b>
      {children}
    </div>
  );
}
