export const GOALS = [
  { code: "weight_loss", label: "Perdre du poids", sub: "Brûler, tonifier, retrouver du souffle" },
  { code: "muscle", label: "Prendre du muscle", sub: "Musculation, prise de masse" },
  { code: "restart", label: "Me remettre au sport", sub: "Reprendre sans pression" },
  { code: "cardio", label: "Cardio et endurance", sub: "Course, vélo, circuit" },
  { code: "combat", label: "Sports de combat", sub: "Boxe, MMA, lutte" },
  { code: "dance", label: "Danse et fitness", sub: "Zumba, afro, cours collectifs" },
];
export const goalLabel = (c) => GOALS.find((g) => g.code === c)?.label || c;

export const LEVELS = [
  { code: "debutant", label: "Débutant" },
  { code: "intermediaire", label: "Intermédiaire" },
  { code: "avance", label: "Avancé" },
];
export const levelLabel = (c) => LEVELS.find((l) => l.code === c)?.label || c;

export const PERIODS = [
  { code: "morning", label: "Matin", sub: "5h – 8h" },
  { code: "noon", label: "Midi", sub: "12h – 14h" },
  { code: "evening", label: "Soir", sub: "17h – 20h" },
  { code: "weekend", label: "Week-end", sub: "Toute la journée" },
];
export const periodLabel = (c) => PERIODS.find((p) => p.code === c)?.label || c;

export const DAY_LETTERS = ["L", "M", "M", "J", "V", "S", "D"];
export const DAY_NAMES = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"];
export const DAY_FULL = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"];
export const hhmm = (t) => (t || "").slice(0, 5).replace(/^0/, "");
export const hm = (t) => { const [h, m] = (t || "").split(":"); return `${Number(h)}h${m && m !== "00" ? m : ""}`; };

export const COMMUNES = ["Cocody", "Marcory", "Yopougon", "Plateau", "Treichville", "Abobo", "Adjamé", "Koumassi", "Port-Bouët", "Bingerville"];

export const fmtPrice = (n) => `${Number(n).toLocaleString("fr-FR").replace(/[  ]/g, " ")} F`;

export const CATEGORIES = [
  { code: "weights", label: "Poids" },
  { code: "machines", label: "Machines" },
  { code: "clothing", label: "Tenues" },
  { code: "accessories", label: "Accessoires" },
];
export const categoryLabel = (c) => CATEGORIES.find((x) => x.code === c)?.label || c;
export const CONDITIONS = [
  { code: "new", label: "Neuf" },
  { code: "very_good", label: "Très bon" },
  { code: "ok", label: "Correct" },
];
export const conditionLabel = (c) => ({ new: "Neuf", very_good: "Très bon état", ok: "Correct" }[c] || c);

export const MODE_LABELS = { gym: "En salle", home: "À domicile", online: "En ligne" };
export const modesLabel = (modes = []) => modes.map((m) => MODE_LABELS[m] || m).join(" ou ").toLowerCase();

export const PRO_TYPES = [
  { code: "coach", label: "Coach sportif" },
  { code: "gym", label: "Salle de sport" },
  { code: "nutrition", label: "Nutritionniste, diététicien" },
  { code: "physio", label: "Kinésithérapeute" },
  { code: "doctor", label: "Médecin du sport" },
  { code: "shop", label: "Boutique de matériel" },
];

export const SERVICE_KINDS = [
  { code: "trial", label: "Séance d'essai" },
  { code: "single", label: "Séance" },
  { code: "duo", label: "Séance à deux" },
  { code: "consultation", label: "Consultation" },
  { code: "followup", label: "Suivi" },
  { code: "plan", label: "Plan personnalisé" },
  { code: "workshop", label: "Atelier collectif" },
];

// yyyy-mm-dd en heure locale (et non UTC) pour interroger les créneaux.
export const dateKey = (d) => {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
export const nextDays = (n = 7) => Array.from({ length: n }, (_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return d; });
export const weekdayShort = (d) => WEEKDAY.format(d).replace(".", "");

const pad2 = (n) => String(n).padStart(2, "0");
// Date calendaire AAAA-MM-JJ (sans heure) vers JJ/MM/AAAA, sans décalage de fuseau.
export const fmtDate = (ymd) => (ymd ? ymd.slice(0, 10).split("-").reverse().join("/") : "–");
export const fmtDateTime = (iso) => {
  if (!iso) return "–";
  const d = new Date(iso);
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
};

export const PRO_LABELS = {
  coach: "Coach", gym: "Salle", nutrition: "Nutritionniste", physio: "Kinésithérapeute", doctor: "Médecin du sport", shop: "Boutique",
};

const WEEKDAY = new Intl.DateTimeFormat("fr-FR", { weekday: "short" });
const MONTH = new Intl.DateTimeFormat("fr-FR", { month: "short" });
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export const fmtTime = (iso) => {
  const d = new Date(iso);
  const m = d.getMinutes();
  return `${d.getHours()}h${m ? String(m).padStart(2, "0") : ""}`;
};
export const fmtWhen = (iso) => {
  const d = new Date(iso);
  return `${cap(WEEKDAY.format(d).replace(".", ""))}. ${d.getDate()} ${MONTH.format(d).replace(".", "")} · ${fmtTime(iso)}`;
};
export const dayParts = (iso) => {
  const d = new Date(iso);
  return { day: d.getDate(), weekday: WEEKDAY.format(d).replace(".", "") };
};

export const ago = (iso) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "À l'instant";
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  if (s < 86400) return `${Math.floor(s / 3600)} h`;
  if (s < 7 * 86400) return cap(WEEKDAY.format(new Date(iso)).replace(".", "")) + ".";
  return `${new Date(iso).getDate()} ${MONTH.format(new Date(iso)).replace(".", "")}`;
};

// Valeur d'un <input type="datetime-local"> vers une date ISO (heure locale de l'utilisateur).
export const localToIso = (v) => new Date(v).toISOString();
export const defaultLocalInput = (hoursAhead = 24) => {
  const d = new Date(Date.now() + hoursAhead * 3600 * 1000);
  d.setMinutes(0, 0, 0);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`;
};
