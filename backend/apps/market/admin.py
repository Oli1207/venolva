from django.contrib import admin

from .models import Listing, Report


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "seller", "price", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "seller__display_name", "seller__phone")
    actions = ["hide"]

    @admin.action(description="Retirer les annonces sélectionnées")
    def hide(self, request, queryset):
        queryset.update(status=Listing.Status.HIDDEN)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("listing", "reporter", "reason", "handled", "created_at")
    list_filter = ("reason", "handled")
    actions = ["mark_handled"]

    @admin.action(description="Marquer comme traités")
    def mark_handled(self, request, queryset):
        queryset.update(handled=True)
