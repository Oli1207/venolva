import { useEffect } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Loading, Wordmark } from "../ui";

const STEPS = [
  ["1", "Dis ce que tu veux", "Perdre du poids, prendre de la masse, te remettre en forme. Ton niveau, ta salle, tes jours et tes horaires."],
  ["2", "Rencontre ton binôme", "On te présente des membres près de chez toi qui s'entraînent comme toi, avec un score de compatibilité."],
  ["3", "Fixez une séance", "Vous discutez, vous choisissez un créneau, vous vous retrouvez à la salle. La ponctualité de chacun est visible."],
];

const FEATURES = [
  ["Binômes", "Trouve quelqu'un qui a le même objectif, le même rythme et la même salle que toi."],
  ["Coachs et pros", "Coachs, nutritionnistes, kinés, médecins du sport : profils vérifiés, réservation et paiement mobile money."],
  ["Salles", "Horaires, tarifs, cours collectifs et avis des membres, commune par commune."],
  ["Marché", "Achète et vends haltères, tenues et matériel entre membres, en direct."],
  ["Fil", "Des séances, des conseils et des articles de pros, classés selon ce qui compte pour toi."],
  ["Paiement local", "Wave, Orange Money, MTN MoMo, Moov ou carte. Les pros sont reversés après chaque séance."],
];

function PhoneMock() {
  return (
    <div className="lp-phone" aria-hidden="true">
      <div className="lp-screen">
        <div className="lp-bar"><b>Binômes</b><span>Cocody</span></div>
        {[["AK", "Awa K.", "Perte de poids · Débutant", 92], ["YK", "Yann K.", "Prise de masse · Intermédiaire", 81]].map(([ini, name, sub, score]) => (
          <div className="lp-card" key={name}>
            <div className="lp-av">{ini}</div>
            <div style={{ flex: 1, minWidth: 0 }}><div className="lp-name">{name}</div><div className="lp-sub">{sub}</div></div>
            <div className="lp-score">{score}</div>
          </div>
        ))}
        <div className="lp-post"><b>Séance jambes ce soir, 18h</b><span>Salle Riviera 3 · il reste une place</span><i>Je viens</i></div>
      </div>
    </div>
  );
}

export default function Accueil() {
  const { user, ready } = useAuth();
  useEffect(() => { document.title = "Venolva · Trouve ton binôme de sport à Abidjan"; return () => { document.title = "Venolva"; }; }, []);
  if (!ready) return <Loading />;
  if (user) return <Navigate to={user.profile.onboarded ? "/fil" : "/bienvenue"} replace />;

  return (
    <div className="lp">
      <header className="lp-head">
        <Wordmark />
        <nav aria-label="Accueil">
          <a href="#comment">Comment ça marche</a>
          <a href="#fonctions">Ce qu'on y trouve</a>
          <Link to="/connexion" className="lp-btn dark">Se connecter</Link>
        </nav>
      </header>

      <section className="lp-hero">
        <div>
          <p className="lp-kicker">Sport · Abidjan</p>
          <h1>Ta salle.<br />Ton objectif.<br />Ton <span>binôme.</span></h1>
          <p className="lp-lead">Se mettre au sport est plus facile à deux. Venolva te présente quelqu'un qui s'entraîne comme toi, et réunit aussi les coachs, les salles et le matériel dont tu as besoin.</p>
          <div className="lp-cta">
            <Link to="/connexion" className="lp-btn accent">Commencer, c'est gratuit</Link>
            <a href="#comment" className="lp-btn ghost">Voir comment ça marche</a>
          </div>
          <p className="lp-note">Connexion par e-mail, sans mot de passe.</p>
        </div>
        <PhoneMock />
      </section>

      <section id="comment" className="lp-sec">
        <h2>Comment ça marche</h2>
        <ol className="lp-steps">
          {STEPS.map(([n, t, d]) => <li key={n}><span>{n}</span><h3>{t}</h3><p>{d}</p></li>)}
        </ol>
      </section>

      <section id="fonctions" className="lp-sec">
        <h2>Tout le sport au même endroit</h2>
        <div className="lp-grid">
          {FEATURES.map(([t, d]) => <article key={t}><h3>{t}</h3><p>{d}</p></article>)}
        </div>
      </section>

      <section className="lp-sec lp-pro">
        <div>
          <h2>Tu es coach, pro de santé ou gérant de salle ?</h2>
          <p>Crée ton compte, passe en compte pro et fais valider ton dossier. Tu reçois des réservations, tu publies des articles et tu es payé après chaque séance.</p>
        </div>
        <Link to="/connexion" className="lp-btn accent">Rejoindre Venolva</Link>
      </section>

      <footer className="lp-foot">
        <Wordmark size={18} />
        <span>Venolva · Abidjan, Côte d'Ivoire</span>
      </footer>
    </div>
  );
}
