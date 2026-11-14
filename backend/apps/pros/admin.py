from django.contrib import admin

from .models import Booking, ProProfile, Service


@admin.register(ProProfile)
class ProProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "pro_type", "credential", "status", "created_at")
    list_filter = ("status", "user__pro_type")
    search_fields = ("user__display_name", "user__phone", "credential")
    actions = ["approve", "reject"]

    @admin.display(description="Métier")
    def pro_type(self, obj):
        return obj.user.get_pro_type_display()

    @admin.action(description="Valider les dossiers sélectionnés (coche verte)")
    def approve(self, request, queryset):
        for p in queryset:
            p.approve()

    @admin.action(description="Refuser les dossiers sélectionnés")
    def reject(self, request, queryset):
        for p in queryset:
            p.reject("Justificatifs insuffisants.")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "kind", "price", "active")
    list_filter = ("kind", "active")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "service", "client", "pro", "starts_at", "status", "payment_status")
    list_filter = ("status", "payment_status")
