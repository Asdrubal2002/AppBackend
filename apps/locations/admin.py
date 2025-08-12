from django.contrib import admin
from .models import Country, City, Neighborhood
from import_export.admin import ImportExportModelAdmin
from import_export import resources
# Register your models here.

# Recurso para Country
class CountryResource(resources.ModelResource):
    class Meta:
        model = Country
        fields = ('id', 'name', 'code', 'currency_name', 'currency_code')

class CountryAdmin(ImportExportModelAdmin):
    resource_class = CountryResource
    list_display = ('id', 'name', 'code')
    search_fields = ('name', 'code')


# Recurso para City
class CityResource(resources.ModelResource):
    class Meta:
        model = City
        fields = ('id', 'name', 'country__name', 'country')

class CityAdmin(ImportExportModelAdmin):
    resource_class = CityResource
    list_display = ('id', 'name', 'country')
    search_fields = ('name',)
    list_filter = ('country',)

# Recurso para Neighborhood
class NeighborhoodResource(resources.ModelResource):
    class Meta:
        model = Neighborhood
        fields = ('id', 'name', 'city__name', 'city')

class NeighborhoodAdmin(ImportExportModelAdmin):
    resource_class = NeighborhoodResource
    list_display = ('id', 'name', 'city')
    search_fields = ('name',)
    list_filter = ('city',)

# Registramos los modelos en el admin
admin.site.register(Country, CountryAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Neighborhood, NeighborhoodAdmin)