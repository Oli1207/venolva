"""Administration des contenus : publications, annonces, réservations, création de membres et de salles."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from apps.accounts.models import Profile, User, normalize_email
from apps.feed.models import Post
from apps.gyms.models import Gym
from apps.market.models import Listing
from apps.notifications.services import notify
from apps.pros.models import Booking

from .models import audit
from .views import AdminView, bad, gym_row, page, person, user_row


# --- Membres -----------------------------------------------------------------------------------------------------------------------


class AdminUserCreateView(AdminView):
    """POST {email, display_name?, commune?} : crée un compte. La personne se connecte ensuite avec le code reçu par e-mail."""

    def post(self, request):
        try:
            email = normalize_email(str(request.data.get("email", "")))
        except DjangoValidationError as exc:
            return bad(exc.messages[0])
        if User.objects.filter(email=email).exists():
            return bad("Un compte existe déjà avec cet e-mail.")
        user = User.objects.create_user(email=email, display_name=str(request.data.get("display_name", ""))[:60].strip(), commune=str(request.data.get("commune", ""))[:60].strip())
        Profile.objects.get_or_create(user=user)
        audit(request.user, "user.create", f"user:{user.id}")
        return Response(user_row(user), status=status.HTTP_201_CREATED)




# --- Salles ------------------------------------------------------------------------------------------------------------------------


class AdminGymCreateView(AdminView):
    """POST {name, commune, address?, description?} : ajoute une salle (non vérifiée, sans gérant)."""

    def post(self, request):
        name, commune = str(request.data.get("name", "")).strip(), str(request.data.get("commune", "")).strip()
        if len(name) < 2 or not commune:
            return bad("Le nom et la commune sont obligatoires.")
        gym = Gym.objects.create(name=name[:120], commune=commune[:60], address=str(request.data.get("address", ""))[:200].strip(), description=str(request.data.get("description", ""))[:500].strip())
        audit(request.user, "gym.create", f"gym:{gym.id}", name=gym.name)
        return Response(gym_row(gym), status=status.HTTP_201_CREATED)




# --- Publications ------------------------------------------------------------------------------------------------------------------


def post_row(p: Post) -> dict:
    return {
        "id": p.id, "kind": p.kind, "title": p.title, "body": p.body[:300], "hidden": p.hidden, "created_at": p.created_at,
        "author": person(p.author), "reports": p.reports.count(),
    }


class AdminPostsView(AdminView):
    """GET ?q=&kind=&hidden=1&reported=1 : toutes les publications, les plus récentes d'abord."""

    def get(self, request):
        q = request.query_params
        qs = Post.objects.select_related("author").order_by("-created_at")
        if q.get("q"):
            qs = qs.filter(Q(body__icontains=q["q"]) | Q(title__icontains=q["q"]) | Q(author__display_name__icontains=q["q"]) | Q(author__email__icontains=q["q"]))
        if q.get("kind") in dict(Post.Kind.choices):
            qs = qs.filter(kind=q["kind"])
        if q.get("hidden") == "1":
            qs = qs.filter(hidden=True)
        if q.get("reported") == "1":
            qs = qs.filter(reports__isnull=False).distinct()
        return page(request, qs, post_row)


class AdminPostActionView(AdminView):
    """POST /admin/posts/<id>/<action>/ avec action = hide | show | delete."""

    def post(self, request, pk, action):
        post = get_object_or_404(Post.objects.select_related("author"), pk=pk)
        if action == "hide":
            post.hidden = True
            post.save(update_fields=["hidden"])
            notify(post.author, "post_hidden", "Une de tes publications a été masquée", "Elle ne respectait pas les règles de Venolva.", "")
        elif action == "show":
            post.hidden = False
            post.save(update_fields=["hidden"])
        elif action == "delete":
            post.delete()
        else:
            return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        audit(request.user, f"post.{action}", f"post:{pk}")
        return Response({"ok": True})


# --- Annonces du marché --------------------------------------------------------------------------------------------------------------


def listing_row(l: Listing) -> dict:
    return {"id": l.id, "title": l.title, "price": l.price, "status": l.status, "category": l.category, "created_at": l.created_at, "seller": person(l.seller)}


class AdminListingsView(AdminView):
    """GET ?q=&status=active|sold|hidden : toutes les annonces."""

    def get(self, request):
        q = request.query_params
        qs = Listing.objects.select_related("seller").order_by("-created_at")
        if q.get("q"):
            qs = qs.filter(Q(title__icontains=q["q"]) | Q(seller__display_name__icontains=q["q"]) | Q(seller__email__icontains=q["q"]))
        if q.get("status") in dict(Listing.Status.choices):
            qs = qs.filter(status=q["status"])
        return page(request, qs, listing_row)


class AdminListingActionView(AdminView):
    """POST /admin/listings/<id>/<action>/ avec action = hide | restore."""

    def post(self, request, pk, action):
        item = get_object_or_404(Listing, pk=pk)
        if action == "hide":
            item.status = Listing.Status.HIDDEN
        elif action == "restore":
            item.status = Listing.Status.ACTIVE
        else:
            return bad("Action inconnue.", status.HTTP_404_NOT_FOUND)
        item.save(update_fields=["status"])
        audit(request.user, f"listing.{action}", f"listing:{pk}")
        return Response(listing_row(item))


# --- Réservations (lecture seule, pour le support) -----------------------------------------------------------------------------------


def booking_row(b: Booking) -> dict:
    return {
        "id": b.id, "service": b.service.name, "pro": person(b.pro), "client": person(b.client), "starts_at": b.starts_at, "status": b.status,
        "payment_status": b.payment_status, "payment_method": b.payment_method, "price_total": b.price_total, "price_client": b.price_client, "created_at": b.created_at,
    }


class AdminBookingsView(AdminView):
    """GET ?q=&status=&payment=&when=past|upcoming : les réservations de pros."""

    def get(self, request):
        q = request.query_params
        qs = Booking.objects.select_related("service", "pro", "client").order_by("-starts_at")
        if q.get("q"):
            qs = qs.filter(Q(pro__display_name__icontains=q["q"]) | Q(client__display_name__icontains=q["q"]) | Q(pro__email__icontains=q["q"]) | Q(client__email__icontains=q["q"]))
        if q.get("status") in dict(Booking.Status.choices):
            qs = qs.filter(status=q["status"])
        if q.get("payment") in dict(Booking.Payment.choices):
            qs = qs.filter(payment_status=q["payment"])
        return page(request, qs, booking_row)
