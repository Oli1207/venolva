import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

// Charge une ressource GET et expose { data, error, loading, reload }.
// Un rechargement du même chemin garde les données affichées (pas de clignotement) ; un autre chemin repasse en chargement.
export function useFetch(path, { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: enabled, path });
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);

  const load = useCallback(async () => {
    if (!enabled) return;
    setState((s) => ({ ...s, loading: s.path !== path || s.data === null, error: null, path }));
    try {
      const data = await api.get(path);
      if (alive.current) setState((s) => (s.path === path ? { data, error: null, loading: false, path } : s));
    } catch (error) {
      if (alive.current) setState((s) => (s.path === path ? { data: null, error, loading: false, path } : s));
    }
  }, [path, enabled]);

  useEffect(() => { load(); }, [load]);
  return { ...state, reload: load };
}

// Exécute une action asynchrone en gardant l'état d'attente et l'erreur.
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = useCallback(async (fn) => {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError(e.message || "Une erreur est survenue.");
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run, setError };
}
