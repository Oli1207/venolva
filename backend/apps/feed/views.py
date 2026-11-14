from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.meetups.serializers import MeetupSerializer
from apps.meetups.views import create_meetup

from .models import Post


class PostSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    gym_name = serializers.CharField(source="gym.name", read_only=True, default=None)

    class Meta:
        model = Post
        fields = ["id", "author", "kind", "body", "gym", "gym_name", "starts_at", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

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

    def validate(self, attrs):
        if attrs.get("kind") == Post.Kind.BUDDY:
            start = attrs.get("starts_at")
            if not start or start <= timezone.now():
                raise serializers.ValidationError({"starts_at": "Indique une heure de séance dans le futur."})
        else:
            attrs["starts_at"] = None
        return attrs


class PostListCreateView(ListCreateAPIView):
    """Un seul format de publication pour tout le monde : membre, coach, salle, nutritionniste."""

    serializer_class = PostSerializer

    def get_queryset(self):
        qs = Post.objects.select_related("author", "gym")
        kind = self.request.query_params.get("kind")
        if kind in dict(Post.Kind.choices):
            qs = qs.filter(kind=kind)
        pros = self.request.query_params.get("pros")
        if pros == "1":
            qs = qs.exclude(author__pro_type="").filter(author__pro_verified=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PostJoinView(APIView):
    """POST /api/posts/<id>/join/ : « Je viens » sur une demande de binôme, crée une séance en attente."""

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk, kind=Post.Kind.BUDDY)
        if post.author_id == request.user.pk:
            return Response({"detail": "C'est ta propre demande."}, status=status.HTTP_400_BAD_REQUEST)
        if post.starts_at <= timezone.now():
            return Response({"detail": "Cette séance est déjà passée."}, status=status.HTTP_400_BAD_REQUEST)
        meetup = create_meetup(request.user, post.author, post.starts_at, post.gym, "")
        return Response(MeetupSerializer(meetup, context={"request": request}).data, status=status.HTTP_201_CREATED)
