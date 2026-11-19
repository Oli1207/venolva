import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Loading } from "./ui";
import AdminShell from "./admin/AdminShell";
import Ambassadors from "./admin/Ambassadors";
import Applications from "./admin/Applications";
import Dashboard from "./admin/Dashboard";
import AdminGyms from "./admin/Gyms";
import Journal from "./admin/Journal";
import Moderation from "./admin/Moderation";
import AdminPayments from "./admin/Payments";
import Payouts from "./admin/Payouts";
import Settings from "./admin/Settings";
import Annonces from "./admin/Annonces";
import Promo from "./admin/Promo";
import Publications from "./admin/Publications";
import Reservations from "./admin/Reservations";
import Signalements from "./admin/Signalements";
import Users from "./admin/Users";
import ALaUne from "./pages/ALaUne";
import EditerProfil from "./pages/EditerProfil";
import Notifications from "./pages/Notifications";
import Publication from "./pages/Publication";
import Reglages from "./pages/Reglages";
import Accueil from "./pages/Accueil";
import Ambassadrice from "./pages/Ambassadrice";
import Article from "./pages/Article";
import Binomes from "./pages/Binomes";
import Conversation from "./pages/Conversation";
import DevenirPro from "./pages/DevenirPro";
import EspacePro from "./pages/EspacePro";
import Fil from "./pages/Fil";
import Login from "./pages/Login";
import MaSalle from "./pages/MaSalle";
import MesAnnonces from "./pages/Marche";
import Membre from "./pages/Membre";
import Messages from "./pages/Messages";
import Onboarding from "./pages/Onboarding";
import PaiementRetour from "./pages/PaiementRetour";
import ProProfil from "./pages/ProProfil";
import Profil from "./pages/Profil";
import Pros from "./pages/Pros";
import Publier from "./pages/Publier";
import Reserver from "./pages/Reserver";
import Revenus from "./pages/Revenus";
import SalleProfil from "./pages/SalleProfil";
import Salles from "./pages/Salles";
import Seances from "./pages/Seances";
import Vendre from "./pages/Vendre";

// L'app mobile tient dans une colonne étroite ; l'administration, conçue pour un ordinateur, utilise toute la largeur.
function MobileShell() {
  return <div className="app"><Outlet /></div>;
}

function Protected() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/connexion" replace />;
  if (!user.profile.onboarded) return <Navigate to="/bienvenue" replace />;
  return <Outlet />;
}

function Guest() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (user) return <Navigate to={user.profile.onboarded ? "/fil" : "/bienvenue"} replace />;
  return <Outlet />;
}

function Setup() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/connexion" replace />;
  if (user.profile.onboarded) return <Navigate to="/fil" replace />;
  return <Onboarding />;
}

function StaffOnly() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to="/connexion" replace />;
  if (!user.is_staff) return <Navigate to="/fil" replace />;
  return <AdminShell />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/admin" element={<StaffOnly />}>
        <Route index element={<Dashboard />} />
        <Route path="reglages" element={<Settings />} />
        <Route path="paiements" element={<AdminPayments />} />
        <Route path="reversements" element={<Payouts />} />
        <Route path="dossiers" element={<Applications />} />
        <Route path="ambassadeurs" element={<Ambassadors />} />
        <Route path="salles" element={<AdminGyms />} />
        <Route path="moderation" element={<Moderation />} />
        <Route path="a-la-une" element={<Promo />} />
        <Route path="signalements" element={<Signalements />} />
        <Route path="publications" element={<Publications />} />
        <Route path="annonces" element={<Annonces />} />
        <Route path="reservations" element={<Reservations />} />
        <Route path="utilisateurs" element={<Users />} />
        <Route path="journal" element={<Journal />} />
      </Route>
      <Route path="/" element={<Accueil />} />
      <Route element={<MobileShell />}>
        <Route element={<Guest />}><Route path="/connexion" element={<Login />} /></Route>
        <Route path="/bienvenue" element={<Setup />} />
        <Route element={<Protected />}>
          <Route path="/fil" element={<Fil />} />
          <Route path="/publier" element={<Publier />} />
          <Route path="/binomes" element={<Binomes />} />
          <Route path="/membres/:id" element={<Membre />} />
          <Route path="/seances" element={<Seances />} />
          <Route path="/messages" element={<Messages />} />
          <Route path="/messages/:id" element={<Conversation />} />
          <Route path="/profil" element={<Profil />} />
          <Route path="/profil/modifier" element={<EditerProfil />} />
          <Route path="/reglages" element={<Reglages />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/a-la-une" element={<ALaUne />} />
          <Route path="/publication/:id" element={<Publication />} />
          <Route path="/marche/:id" element={<Article />} />
          <Route path="/vendre" element={<Vendre />} />
          <Route path="/mes-annonces" element={<MesAnnonces />} />
          <Route path="/paiement/retour" element={<PaiementRetour />} />
          <Route path="/revenus" element={<Revenus />} />
          <Route path="/ambassadrice" element={<Ambassadrice />} />
          <Route path="/salles" element={<Salles />} />
          <Route path="/salles/:id" element={<SalleProfil />} />
          <Route path="/ma-salle" element={<MaSalle />} />
          <Route path="/pros" element={<Pros />} />
          <Route path="/pros/:id" element={<ProProfil />} />
          <Route path="/pros/:id/reserver" element={<Reserver />} />
          <Route path="/pro" element={<EspacePro />} />
          <Route path="/pro/devenir" element={<DevenirPro />} />
        </Route>
        <Route path="*" element={<Navigate to="/fil" replace />} />
      </Route>
    </Routes>
  );
}
