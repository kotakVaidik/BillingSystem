from django.contrib import admin
from .models import OTPToken, DistributorProfile


@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display  = ('user', 'otp', 'created_at', 'is_used', 'is_expired')
    list_filter   = ('is_used',)
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('otp', 'created_at')
    ordering      = ('-created_at',)

    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired?'


@admin.register(DistributorProfile)
class DistributorProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'phone')
    search_fields = ('user__email', 'user__username', 'phone')


from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ('name', 'phone', 'email', 'distributor', 'created_at')
    search_fields = ('name', 'phone', 'email', 'distributor__username', 'distributor__email')
    list_filter   = ('created_at',)

