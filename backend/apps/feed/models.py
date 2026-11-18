from django.conf import settings
from django.db import models


class Post(models.Model):
    """Une publication simple : du texte, et au plus une demande de binôme."""

    class Kind(models.TextChoices):
        TEXT = "text", "Publication"
        BUDDY = "buddy", "Cherche un binôme"
        ARTICLE = "article", "Article"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.TEXT)
    title = models.CharField(max_length=120, blank=True)  # seulement pour un article
    body = models.CharField(max_length=5000)  # 600 caractères pour une publication, 5000 pour un article
    gym = models.ForeignKey("gyms.Gym", null=True, blank=True, on_delete=models.SET_NULL)
    starts_at = models.DateTimeField(null=True, blank=True)  # pour une demande de binôme
    hidden = models.BooleanField(default=False, db_index=True)  # masquée par la modération
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "user"], name="one_like_per_user")]


class PostImpression(models.Model):
    """Ce qu'un membre a déjà vu : sert à ne pas lui remontrer toujours les mêmes publications."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="impressions")
    seen = models.PositiveSmallIntegerField(default=1)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="one_impression_per_pair")]
