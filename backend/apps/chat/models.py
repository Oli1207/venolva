from django.conf import settings
from django.db import models


class Conversation(models.Model):
    """Discussion entre deux personnes, éventuellement liée à une séance."""

    user_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    user_b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    meetup = models.ForeignKey("meetups.Meetup", null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["user_a", "user_b"], name="unique_pair")]

    @staticmethod
    def ordered(u1, u2):
        """Toujours (plus petit id, plus grand id) pour qu'une paire n'existe qu'une fois."""
        return (u1, u2) if u1.pk < u2.pk else (u2, u1)

    def involves(self, user) -> bool:
        return user.pk in (self.user_a_id, self.user_b_id)

    def other(self, user):
        return self.user_b if user.pk == self.user_a_id else self.user_a


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    body = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
