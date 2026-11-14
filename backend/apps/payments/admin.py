from django.contrib import admin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "purpose", "amount", "provider", "method", "status", "created_at")
    list_filter = ("status", "provider", "purpose")
    search_fields = ("reference", "user__phone", "user__display_name")
    readonly_fields = [f.name for f in Payment._meta.fields]  # on ne modifie jamais un paiement à la main

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "provider", "event", "reference", "outcome", "signature_valid")
    list_filter = ("provider", "outcome", "signature_valid")
    readonly_fields = [f.name for f in WebhookEvent._meta.fields]

    def has_add_permission(self, request):
        return False
