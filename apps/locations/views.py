from django.shortcuts import render
from rest_framework import generics
from .models import Country, City, Neighborhood
from .serializers import CountrySerializer, CitySerializer, NeighborhoodSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny

# Create your views here.

class CountryListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    pagination_class = None  # 👈 Desactiva paginación

class CityListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CitySerializer
    pagination_class = None  
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['country']

    def get_queryset(self):
        return City.objects.all()

class NeighborhoodListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = NeighborhoodSerializer
    pagination_class = None  
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['city']

    def get_queryset(self):
        return Neighborhood.objects.all()


