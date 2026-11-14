from .models import Conversation


def get_or_create_conversation(u1, u2):
    a, b = Conversation.ordered(u1, u2)
    conv, _ = Conversation.objects.get_or_create(user_a=a, user_b=b)
    return conv
