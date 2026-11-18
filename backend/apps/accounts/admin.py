from django.contrib import admin

from .models import Profile, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "phone", "display_name", "commune", "pro_type", "pro_verified", "date_joined")
    list_filter = ("pro_type", "pro_verified")
    search_fields = ("email", "phone", "display_name")
    actions = ["verify_pros"]

    @admin.action(description="Valider les comptes pro sélectionnés (coche verte)")
    def verify_pros(self, request, queryset):
        queryset.exclude(pro_type="").update(pro_verified=True)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "gym", "onboarded")
    list_filter = ("level", "onboarded")
