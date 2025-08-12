from django.contrib import admin
from .models import (Store, 
                     Review, 
                     Category, 
                     CategoryProduct, 
                     StoreSchedule, 
                     ShippingMethod,
                     ShippingMethodZone,
                     ShippingZone,
                     PaymentMethod,

                     Coupon,
                      Combo, 
                    ComboItem
                     )
from import_export import resources
from import_export.admin import ExportMixin, ImportExportModelAdmin

class StoreScheduleInline(admin.TabularInline):
    model = StoreSchedule
    extra = 1  # Número de formularios vacíos para agregar

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'slug', 'country', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'country', 'city')
    search_fields = ('name', 'slug', 'nit', 'legal_name')
    readonly_fields = ('created_at', 'updated_at', 'average_rating', 'total_visits', 'slug')

    filter_horizontal = ('administrators',)  # Para seleccionar varios usuarios de forma cómoda

    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'slug', 'description', 'nit', 'legal_name', 'foundation_date','category')
        }),
        ('Ubicación', {
            'fields': ('country', 'city', 'neighborhood', 'address','location')
        }),
        ('Multimedia', {
            'fields': ('logo', 'banner')
        }),
        ('Administradores', {
            'fields': ('administrators','first_admin')
        }),
        ('Estado y Métricas', {
            'fields': ('is_active', 'average_rating', 'total_visits', 'created_at', 'updated_at','is_verified')
        }),
    
    )
    inlines = [StoreScheduleInline]
    
admin.site.register(StoreSchedule)  
  
      
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('store', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('store__name', 'user__username', 'comment')
    readonly_fields = ('created_at',)

    fieldsets = (
        (None, {
            'fields': ('store', 'user', 'rating', 'comment')
        }),
        ('Tiempos', {
            'fields': ('created_at',)
        }),
    )


class CategoryResource(resources.ModelResource):
    class Meta:
        model = Category
        fields = ('id', 'name', 'type', 'icon_name', 'slug')
        export_order = ('id', 'name', 'type', 'icon_name', 'slug')

@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    resource_class = CategoryResource
    list_display = ('id', 'name', 'slug', 'type')
    search_fields = ('name',)
    readonly_fields = ('slug',)
    
@admin.register(CategoryProduct)
class CategoryProductdmin(admin.ModelAdmin):
    list_display = ('id','name', 'parent','store')

    search_fields = ('name',)
    readonly_fields = ('slug',)

admin.site.register(ShippingMethod)  
admin.site.register(ShippingMethodZone)  

admin.site.register(ShippingZone)  

admin.site.register(PaymentMethod)  

admin.site.register(Coupon)  


admin.site.register(Combo)  
admin.site.register(ComboItem)  


