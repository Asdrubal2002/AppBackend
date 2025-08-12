import django_filters
from .models import Store

class StoreFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains')
    country = django_filters.NumberFilter(field_name='country__id')
    city = django_filters.NumberFilter(field_name='city__id')
    neighborhood = django_filters.NumberFilter(field_name='neighborhood__id')
    is_active = django_filters.BooleanFilter(field_name='is_active')
    category = django_filters.NumberFilter(field_name='category__id') 
    
    class Meta:
        model = Store
        fields = ['name', 'country', 'city', 'neighborhood', 'is_active', 'category']
