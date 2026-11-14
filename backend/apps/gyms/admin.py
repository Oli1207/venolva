from django.contrib import admin

from .models import Gym, GymClass, GymHours, GymPlan, GymReview, MembershipRequest


class HoursInline(admin.TabularInline):
    model = GymHours
    extra = 0


class PlanInline(admin.TabularInline):
    model = GymPlan
    extra = 0


@admin.register(Gym)
class GymAdmin(admin.ModelAdmin):
    list_display = ("name", "commune", "owner", "verified")
    list_filter = ("commune", "verified")
    search_fields = ("name", "commune", "owner__display_name", "owner__phone")
    inlines = [HoursInline, PlanInline]  # le champ « owner » permet de rattacher une salle existante à son gérant


@admin.register(GymClass)
class GymClassAdmin(admin.ModelAdmin):
    list_display = ("name", "gym", "starts_at", "capacity", "active")


@admin.register(GymReview)
class GymReviewAdmin(admin.ModelAdmin):
    list_display = ("gym", "user", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(MembershipRequest)
class MembershipRequestAdmin(admin.ModelAdmin):
    list_display = ("plan", "user", "status", "created_at")
    list_filter = ("status",)
