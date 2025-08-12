from django.db import models

class Country(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=5, unique=True)  # Ej: +57, +1
    currency_name = models.CharField(max_length=50, default='Peso Colombiano')  # Ej: Peso Colombiano
    currency_code = models.CharField(max_length=10, default='COP')   

    def __str__(self):
        return f"{self.name} ({self.code})"


class City(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='cities')

    class Meta:
        unique_together = ('name', 'country')  # Para evitar duplicados tipo "Bogotá, Colombia" y "Bogotá, México"

    def __str__(self):
        return f"{self.name}, {self.country.name}"

class Neighborhood(models.Model):
    name = models.CharField(max_length=100)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='neighborhoods')

    class Meta:
        unique_together = ('name', 'city')

    def __str__(self):
        return f"{self.name}, {self.city.name}"