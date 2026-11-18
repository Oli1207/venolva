import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { api } from "../api";
import { useAction, useFetch } from "../hooks";
import { goalLabel, levelLabel } from "../labels";
import { Avatar, Icon, TabBar, Toggle } from "../ui";

export default function Profil() {
  const { user, setUser, logout } = useAuth();
  const me = useFetch(`/members/${user.id}/`);
  const pro = useFetch("/pro/me/");
  const { error, run } = useAction();
  const p = user.profile;

  const update = (patch) => run(async () => setUser(await api.patch("/auth/me/", { profile: patch })));

  return (
    <main className="page">
      <div className="pad" style={{ paddingTop: 36, display: "flex", alignItems: "center", gap: 16 }}>
        <Avatar person={user} size={72} />
        <div style={{ minWidth: 0 }}>
          <div className="h" style={{ fontSize: 26, lineHeight: 1.1 }}>{user.display_name}</div>
          <div style={{ fontSize: 14, color: "#55554f", marginTop: 4 }}>{user.commune}</div>
          <div className="small muted" style={{ marginTop: 2 }}>{p.goals.map(goalLabel).join(", ")} · {levelLabel(p.level)}</div>
        </div>
      </div>

      <div className="stats" style={{ paddingTop: 22 }}>
        <div className="stat"><div className="sv" style={{ fontSize: 28 }}>{me.data?.sessions_done ?? "–"}</div><div className="sl">Séances</div></div>
        <div className="stat"><div className="sv" style={{ fontSize: 28 }}>{me.data?.punctuality != null ? String(me.data.punctuality).replace(".", ",") : "–"}</div><div className="sl">Ponctualité</div></div>
      </div>
      {me.data?.punctuality == null && me.data && <p className="hint pad" style={{ margin: "10px 0 0" }}>Ta note de ponctualité apparaît après 3 séances terminées.</p>}

      <div className="rows" style={{ paddingTop: 20 }}>
        <Link to="/profil/modifier" className="row" style={{ minHeight: 64 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15.5 }}>Modifier mon profil</div>
            <div className="small muted" style={{ marginTop: 1 }}>Nom, commune, objectifs, niveau</div>
          </div>
          <Icon name="chevron" size={18} stroke={2} />
        </Link>
        <Link to="/notifications" className="row" style={{ minHeight: 64 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15.5 }}>Notifications</div>
            <div className="small muted" style={{ marginTop: 1 }}>Réservations, séances, paiements</div>
          </div>
          <Icon name="chevron" size={18} stroke={2} />
        </Link>
        <Link to="/a-la-une" className="row" style={{ minHeight: 64 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15.5 }}>À la une</div>
            <div className="small muted" style={{ marginTop: 1 }}>Mettre un contenu en avant, voir les résultats</div>
          </div>
          <Icon name="chevron" size={18} stroke={2} />
        </Link>
        {p.gym && (
          <Link to={`/salles/${p.gym}`} className="row" style={{ minHeight: 64 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15.5 }}>Ma salle</div>
              <div className="small muted" style={{ marginTop: 1 }}>Horaires, tarifs, cours et avis</div>
            </div>
            <Icon name="chevron" size={18} stroke={2} />
          </Link>
        )}
        {user.is_staff && (
          <Link to="/admin" className="row" style={{ minHeight: 64 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15.5 }}>Administration</div>
              <div className="small muted" style={{ marginTop: 1 }}>Réglages, paiements, reversements, modération</div>
            </div>
            <Icon name="chevron" size={18} stroke={2} />
          </Link>
        )}
        {user.is_ambassador && (
          <Link to="/ambassadrice" className="row" style={{ minHeight: 64 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15.5 }}>Espace ambassadrice</div>
              <div className="small muted" style={{ marginTop: 1 }}>Mon contrat, mes gains et mes relevés</div>
            </div>
            <Icon name="chevron" size={18} stroke={2} />
          </Link>
        )}
        {user.pro_verified && (
          <Link to="/revenus" className="row" style={{ minHeight: 64 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: 15.5 }}>Mes revenus</div>
              <div className="small muted" style={{ marginTop: 1 }}>Solde, reversements et compte de réception</div>
            </div>
            <Icon name="chevron" size={18} stroke={2} />
          </Link>
        )}
        <Link to="/mes-annonces" className="row" style={{ minHeight: 64 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15.5 }}>Mes annonces</div>
            <div className="small muted" style={{ marginTop: 1 }}>Ce que je vends sur le marché</div>
          </div>
          <Icon name="chevron" size={18} stroke={2} />
        </Link>
        <Link to={user.pro_verified ? "/pro" : "/pro/devenir"} className="row" style={{ minHeight: 64 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: 15.5 }}>{user.pro_verified ? "Espace pro" : pro.data?.status === "pending" ? "Compte pro en vérification" : "Passer en compte pro"}</div>
            <div className="small muted" style={{ marginTop: 1 }}>{user.pro_verified ? "Réservations, services et horaires" : "Coach, nutritionniste, kiné, médecin du sport"}</div>
          </div>
          <Icon name="chevron" size={18} stroke={2} />
        </Link>
      </div>

      <div className="rows" style={{ paddingTop: 20 }}>
        <div className="k" style={{ paddingBottom: 2 }}>Confidentialité</div>
        <div className="row" style={{ cursor: "default" }}><span style={{ flex: 1 }}>Visible dans les binômes</span><Toggle on={p.visible} onChange={(v) => update({ visible: v })} label="Visible dans les binômes" /></div>
        <div className="row" style={{ cursor: "default" }}><span style={{ flex: 1 }}>Afficher ma ponctualité</span><Toggle on={p.show_punctuality} onChange={(v) => update({ show_punctuality: v })} label="Afficher ma ponctualité" /></div>
      </div>
      {error && <p className="error pad" role="alert">{error}</p>}

      <div className="pad" style={{ marginTop: "auto", paddingTop: 28, paddingBottom: 24, display: "flex", flexDirection: "column", gap: 12 }}>
        <Link to="/reglages" className="link" style={{ fontSize: 15 }}>Réglages, membres bloqués, supprimer mon compte</Link>
        <div className="small muted">Connecté avec {user.email}</div>
        <button type="button" className="btn ghost" style={{ height: 52, fontSize: 15.5 }} onClick={logout}>Se déconnecter</button>
      </div>
      <TabBar />
    </main>
  );
}
