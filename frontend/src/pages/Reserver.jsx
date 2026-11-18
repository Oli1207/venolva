import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { MODE_LABELS, dateKey, fmtPrice, fmtTime, nextDays, weekdayShort } from "../labels";
import { Avatar, BackButton, Empty, Loading } from "../ui";

export default function Reserver() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const nav = useNavigate();
  const { data: pro, loading, error } = useFetch(`/pros/${id}/`);
  const { busy, error: bookError, run } = useAction();

  const [serviceId, setServiceId] = useState(params.get("service") || null);
  const days = useMemo(() => nextDays(8), []);
  const [day, setDay] = useState(dateKey(days[0]));
  const [slots, setSlots] = useState(null);
  const [time, setTime] = useState("");
  const [mode, setMode] = useState("");
  const [partner, setPartner] = useState("");

  const service = pro?.services.find((s) => s.id === (serviceId ?? pro.services[0]?.id));
  const duo = service?.kind === "duo";
  const matches = useFetch("/matches/?min=0", { enabled: !!duo });
  const methods = useFetch("/payments/methods/");

  useEffect(() => { if (service) setMode((m) => (service.modes.includes(m) ? m : service.modes[0])); }, [service]);
  useEffect(() => {
    if (!service) return;
    let alive = true;
    setSlots(null);
    setTime("");
    api.get(`/pros/${id}/slots/?service=${service.id}&date=${day}`).then((s) => alive && setSlots(s)).catch(() => alive && setSlots([]));
    return () => { alive = false; };
  }, [id, service?.id, day]);

  if (loading) return <main className="page bare"><div className="topbar"><BackButton /></div><Loading /></main>;
  if (error || !service) return <main className="page bare"><div className="topbar"><BackButton /></div><Empty title="Réservation impossible">{error?.message || "Ce pro n'a pas encore de service."}</Empty></main>;

  const myPart = duo ? Math.ceil(service.price / 2) : service.price;
  const ready = time && (!duo || partner);

  const submit = () =>
    run(async () => {
      await api.post("/bookings/", {
        service: service.id, starts_at: time, mode, payment_method: "cash",
        ...(duo ? { partner } : {}),
      });
      nav("/seances?tab=bookings", { replace: true });
    });

  return (
    <main className="page bare" style={{ paddingBottom: 150 }}>
      <div className="topbar"><BackButton /><h1 className="h" style={{ fontSize: 26, lineHeight: 1 }}>Réserver</h1></div>

      <div className="pad" style={{ paddingTop: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 0", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}>
          <Avatar person={pro.person} size={44} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15 }}>{service.name}</div>
            <div className="small muted" style={{ marginTop: 1 }}>{pro.person.display_name} · {service.duration_min} min{service.gym_name ? ` · ${service.gym_name}` : ""}</div>
          </div>
          <span className="price" style={{ fontSize: 16 }}>{fmtPrice(service.price)}</span>
        </div>
        {pro.services.length > 1 && (
          <div className="chips" style={{ marginTop: 12 }}>
            {pro.services.map((s) => <button key={s.id} type="button" className={`chip ${s.id === service.id ? "on" : ""}`} style={{ height: 36, fontSize: 13.5 }} onClick={() => setServiceId(s.id)}>{s.name}</button>)}
          </div>
        )}
      </div>

      <div className="pad" style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="k">Jour</div>
        <div className="daystrip" role="group" aria-label="Jour">
          {days.map((d) => (
            <button key={dateKey(d)} type="button" className={`dsel ${dateKey(d) === day ? "on" : ""}`} aria-pressed={dateKey(d) === day} onClick={() => setDay(dateKey(d))}>
              <span className="d">{weekdayShort(d)}</span><span className="n">{d.getDate()}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="pad" style={{ paddingTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        <div className="k">Heure</div>
        {slots === null ? <Loading text="Recherche des créneaux…" /> : slots.length === 0 ? (
          <p className="hint">Aucun créneau libre ce jour-là. Essaie un autre jour.</p>
        ) : (
          <div className="times" role="group" aria-label="Heure">
            {slots.map((s) => <button key={s} type="button" className={`time ${time === s ? "on" : ""}`} aria-pressed={time === s} onClick={() => setTime(s)}>{fmtTime(s)}</button>)}
          </div>
        )}
      </div>

      {service.modes.length > 1 && (
        <div className="pad" style={{ paddingTop: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          <div className="k">Où</div>
          <div className="chips">{service.modes.map((m) => <button key={m} type="button" className={`chip ${mode === m ? "on" : ""}`} onClick={() => setMode(m)}>{MODE_LABELS[m]}</button>)}</div>
        </div>
      )}

      {duo && (
        <div className="pad" style={{ paddingTop: 16 }}>
          <div className="field">
            <label className="k" htmlFor="partner">Venir avec</label>
            <select id="partner" className="input" value={partner} onChange={(e) => setPartner(e.target.value)}>
              <option value="">Choisir un binôme</option>
              {(matches.data || []).map((m) => <option key={m.id} value={m.id}>{m.display_name}</option>)}
            </select>
            <span className="hint">{fmtPrice(myPart)} chacun. Ton binôme est prévenu de la réservation.</span>
          </div>
        </div>
      )}

      <div className="pad" style={{ paddingTop: 18, display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="k">Paiement</div>
        <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.5, color: "var(--ink-2)" }}>
          {pro.person.display_name} confirme d'abord ta demande. Tu pourras ensuite payer en ligne
          {methods.data?.length ? ` (${methods.data.map((m) => m.label).join(", ")})` : ""}, ou sur place pendant la séance.
        </p>
      </div>

      <div className="bottombar" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
        {bookError && <p className="error" role="alert">{bookError}</p>}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span className="small muted">{duo ? "Ta part" : "Total"}</span>
          <span className="price" style={{ fontSize: 22 }}>{fmtPrice(myPart)}</span>
        </div>
        <button type="button" className="btn" disabled={!ready || busy} onClick={submit}>{busy ? "Envoi…" : "Demander cette séance"}</button>
      </div>
    </main>
  );
}
