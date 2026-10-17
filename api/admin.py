from django.contrib import admin
from .models import UserSecure, AllowedCountries, HelpArticle, JobPosition, JobApplication, TeamMember, PremiumStoreLayout, StoreLayoutPurchase

class JobPositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'department', 'location', 'job_type', 'is_active', 'created_at')
    list_filter = ('is_active', 'department', 'job_type', 'location')
    search_fields = ('title', 'department')

class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'job', 'email', 'applied_at')
    list_filter = ('job',)
    search_fields = ('full_name', 'email')
    readonly_fields = ('job', 'full_name', 'email', 'resume_link', 'cover_letter', 'applied_at')

    def has_add_permission(self, request):
        return False

admin.site.register(UserSecure)
admin.site.register(AllowedCountries)
admin.site.register(HelpArticle)
admin.site.register(JobPosition, JobPositionAdmin)
admin.site.register(JobApplication, JobApplicationAdmin)

class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'department', 'order', 'is_active')
    list_filter = ('department', 'is_active')
    search_fields = ('name', 'role')

admin.site.register(TeamMember, TeamMemberAdmin)

class PremiumStoreLayoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'layout_id', 'price_ngn', 'is_active', 'updated_at')
    list_editable = ('price_ngn', 'is_active')
    search_fields = ('name', 'layout_id')

admin.site.register(PremiumStoreLayout, PremiumStoreLayoutAdmin)

class StoreLayoutPurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'layout_id', 'amount_paid', 'currency', 'amount_in_ngn', 'purchased_at')
    list_filter = ('layout_id', 'currency', 'purchased_at')
    search_fields = ('user__user_email', 'layout_id')
    readonly_fields = ('user', 'business', 'layout_id', 'amount_paid', 'currency', 'amount_in_ngn', 'exchange_rate', 'purchased_at')

admin.site.register(StoreLayoutPurchase, StoreLayoutPurchaseAdmin)
