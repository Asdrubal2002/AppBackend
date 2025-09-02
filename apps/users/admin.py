from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Device
# Register your models here.

class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ('username', 'name', 'cellphone', 'email', 'is_seller', 'is_buyer', 'is_admin')
    list_filter = ('is_seller', 'is_buyer', 'is_admin', 'is_active')
    search_fields = ('username', 'name', 'cellphone', 'email')
    ordering = ('username',)
    readonly_fields = ('registration_date', 'last_login', 'updated_at')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': (
            'name', 'last_name', 'cellphone', 'email', 'date_of_birth', 'gender',
            'document_number', 'address', 'country', 'city', 'neighborhood',
            'followed_stores'
        )}),
        ('Permisos', {'fields': ('is_seller', 'is_buyer', 'is_admin', 'is_active', 'is_staff', 'is_superuser')}),
        ('Verificaciones', {'fields': ('verified_cellphone', 'verified_mail')}),
        ('Fechas', {'fields': ('last_login', 'registration_date')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'name', 'cellphone', 'email', 'password1', 'password2'),
        }),
    )

admin.site.register(User, UserAdmin)
admin.site.register(Device)
