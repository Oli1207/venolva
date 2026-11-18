from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.meetups.serializers import MeetupSerializer
from apps.meetups.views import create_meetup
from apps.notifications.services import notify
from apps.promo import services as promo
from apps.safety.services import blocked_ids

from . import ranking
from .models import Post, PostLike

POST_MAX = 600
ARTICLE_MAX = 5000
EXCERPT = 240


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    gym_name = serializers.CharField(source="gym.name", read_only=True, default=None)
    body = serializers.CharField(max_length=ARTICLE_MAX)
    truncated = serializers.SerializerMethodField()
    mine = serializers.SerializerMethodField()
    likes = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "author", "kind", "title", "body", "gym", "gym_name", "starts_at", "created_at", "truncated", "mine", "likes", "liked"]
        read_only_fields = ["id", "author", "created_at", "truncated", "mine", "likes", "liked"]

    def get_author(self, obj):
        a = obj.author
        return {
            "id": a.id,
            "display_name": a.display_name,
            "initials": a.initials,
            "commune": a.commune,
            "pro_type": a.pro_type,
            "pro_verified": a.pro_verified,
        }

    def get_mine(self, obj):
        req = self.context.get("request")
        return bool(req and obj.author_id == req.user.pk)

    def get_likes(self, obj):
        n = getattr(obj, "n_likes", None)
        return n if n is not None else obj.likes.count()

    def get_liked(self, obj):
        req = self.context.get("request")
        liked = self.context.get("liked")
        if liked is not None:
            return obj.pk in liked
        return bool(req and req.user.is_authenticated and obj.likes.filter(user=req.user).exists())

    def get_truncated(self, obj):
        return obj.kind == Post.Kind.ARTICLE and len(obj.body) > EXCERPT and not self.context.get("full")

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if data["truncated"]:
            data["body"] = obj.body[:EXCERPT].rstrip() + "…"  # la liste n'envoie qu'un extrait
        return data

    def validate(self, attrs):
        kind = attrs.get("kind", Post.Kind.TEXT)
        user = self.context["request"].user
        body = attrs.get("body", "")
        if kind == Post.Kind.ARTICLE:
            if not (user.is_staff or (user.pro_type and user.pro_verified)):
                raise serializers.ValidationError({"kind": "Les articles sont réservés aux professionnels et aux salles validés."})
            if len(attrs.get("title", "").strip()) < 5:
                raise serializers.ValidationError({"title": "Donne un titre à ton article (5 caractères au moins)."})
            if len(body.strip()) < 100:
                raise serializers.ValidationError({"body": "Un article fait au moins 100 caractères."})
            attrs["starts_at"] = None
        else:
            if len(body) > POST_MAX:
                raise serializers.ValidationError({"body": f"{POST_MAX} caractères au maximum."})
            attrs["title"] = ""
            if kind == Post.Kind.BUDDY:
                start = attrs.get("starts_at")
                if not start or start <= timezone.now():
                    raise serializers.ValidationError({"starts_at": "Indique une heure de séance dans le futur."})
            else:
                attrs["starts_at"] = None
        return attrs


class PostListCreateView(ListCreateAPIView):
    """Un seul format de publication pour tout le monde, plus les articles des pros et des salles validés."""

    serializer_class = PostSerializer

    def get_queryset(self):
        qs = Post.objects.select_related("author", "gym").filter(hidden=False)
        hidden = blocked_ids(self.request.user)
        if hidden:
            qs = qs.exclude(author_id__in=hidden)
        kind = self.request.query_params.get("kind")
        if kind in dict(Post.Kind.choices):
            qs = qs.filter(kind=kind)
        if self.request.query_params.get("mine") == "1":
            qs = qs.filter(author=self.request.user)
        pros = self.request.query_params.get("pros")
        if pros == "1":
            qs = qs.exclude(author__pro_type="").filter(author__pro_verified=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PostDetailView(APIView):
    """GET /api/posts/<id>/ : publication complète. DELETE : son auteur ou l'équipe."""

    def get(self, request, pk):
        post = get_object_or_404(Post.objects.select_related("author", "gym"), pk=pk)
        if post.author_id in blocked_ids(request.user) or (post.hidden and post.author_id != request.user.pk and not request.user.is_staff):
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PostSerializer(post, context={"request": request, "full": True}).data)

    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.author_id != request.user.pk and not request.user.is_staff:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostJoinView(APIView):
    """POST /api/posts/<id>/join/ : « Je viens » sur une demande de binôme, crée une séance en attente."""

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk, kind=Post.Kind.BUDDY, hidden=False)
        if post.author_id == request.user.pk:
            return Response({"detail": "C'est ta propre demande."}, status=status.HTTP_400_BAD_REQUEST)
        if post.author_id in blocked_ids(request.user):
            return Response({"detail": "Cette personne n'est pas disponible."}, status=status.HTTP_400_BAD_REQUEST)
        if post.starts_at <= timezone.now():
            return Response({"detail": "Cette séance est déjà passée."}, status=status.HTTP_400_BAD_REQUEST)
        meetup = create_meetup(request.user, post.author, post.starts_at, post.gym, "")
        return Response(MeetupSerializer(meetup, context={"request": request}).data, status=status.HTTP_201_CREATED)


class PostLikeView(APIView):
    """POST : j'aime. DELETE : je retire mon j'aime. Renvoie le compte à jour."""

    def _post(self, request, pk):
        post = get_object_or_404(Post, pk=pk, hidden=False)
        if post.author_id in blocked_ids(request.user):
            from django.http import Http404

            raise Http404
        return post

    def post(self, request, pk):
        post = self._post(request, pk)
        _, created = PostLike.objects.get_or_create(post=post, user=request.user)
        if created and post.author_id != request.user.pk:
            notify(post.author, "post_liked", f"{request.user.display_name or 'Quelqu un'} aime ta publication", (post.title or post.body)[:80], f"/publication/{post.id}")
        return Response({"likes": post.likes.count(), "liked": True})

    def delete(self, request, pk):
        post = self._post(request, pk)
        PostLike.objects.filter(post=post, user=request.user).delete()
        return Response({"likes": post.likes.count(), "liked": False})


class FeedView(APIView):
    """GET /api/feed/?cursor=&size=&kind=&pros=1 : le fil classé pour moi, avec les mises en avant intercalées."""

    def get(self, request):
        q = request.query_params
        try:
            size = int(q.get("size", ranking.PAGE_SIZE))
        except ValueError:
            size = ranking.PAGE_SIZE
        kind = q.get("kind") if q.get("kind") in dict(Post.Kind.choices) else None
        items, nxt = ranking.build_page(request.user, q.get("cursor", ""), size, kind, q.get("pros") == "1")
        post_ids = [i["post"].pk for i in items if i["type"] == "post"]
        liked = set(PostLike.objects.filter(user=request.user, post_id__in=post_ids).values_list("post_id", flat=True))
        ctx = {"request": request, "liked": liked}
        debug = request.user.is_staff and q.get("debug") == "1"
        out = []
        for i in items:
            if i["type"] == "post":
                row = {"type": "post", "post": PostSerializer(i["post"], context=ctx).data}
                if debug:
                    row.update(score=round(i["score"], 4), reasons=i["reasons"])
            else:
                payload = promo.payload(i["feature"])
                if payload is None:
                    continue
                row = {"type": "feature", "feature": payload}
            out.append(row)
        return Response({"results": out, "next": nxt})


class FeedSeenView(APIView):
    """POST {ids: [post ids]} : ce que le membre vient de voir, pour ne pas lui remontrer toujours pareil."""

    def post(self, request):
        ids = request.data.get("ids")
        if not isinstance(ids, list):
            return Response({"detail": "ids doit être une liste."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"recorded": ranking.record_seen(request.user, ids)})
