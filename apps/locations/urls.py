from django.urls import path
from .views import CountryListView, CityListView, NeighborhoodListView

urlpatterns = [
    path('countries/', CountryListView.as_view(), name='country-list'),
    path('cities/', CityListView.as_view(), name='city-list'),
    path('neighborhoods/', NeighborhoodListView.as_view(), name='neighborhood-list'),
]