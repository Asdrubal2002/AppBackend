from django.db import models
from django.utils import timezone
from apps.users.models import User  # modelo User está en la app users
from apps.locations.models import Country, City, Neighborhood
from django.utils.text import slugify
from django.conf import settings
from django.db.models import Avg
import qrcode
from io import BytesIO
from django.core.files import File
from uuid import uuid4
import uuid
from django.core.validators import MaxLengthValidator
from django.contrib.gis.db import models as geomodels

from django.core.exceptions import ValidationError

from ..mongo_utils import get_product_by_id



# Create your models here.

def store_logo_upload_path(instance, filename):
    return f'stores/{instance.slug}/logo/{filename}'

def store_banner_upload_path(instance, filename):
    return f'stores/{instance.slug}/banner/{filename}'

def store_qr_upload_path(instance, filename):
    return f'stores/{instance.slug}/qr/{filename}'

def store_qr_pay(instance, filename):
    return f'stores/{instance.store.slug}/qr-pay/{filename}'

def store_payment_proof(instance, filename):
    return f'stores/{instance.store.id}/orders/{instance.id}/proof/{filename}'

def combo_image_upload(instance, filename):
    return f"stores/{instance.store.slug}/combos/{filename}"

class Category(models.Model):
    TYPE_CHOICES = [
        ('restaurant', 'Restaurante'),
        ('store', 'Tienda'),
        ('service','Servicio')

        # lo que necesites
    ]
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    icon_name = models.CharField(max_length=50, blank=True, null=True)  # Aquí guardas el nombre del icono

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = f"{base_slug}-{str(uuid4())[:8]}"
            self.slug = unique_slug
        super().save(*args, **kwargs)

class Store(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)  # Útil para URLs limpias
    description = models.TextField(blank=True)
    nit = models.CharField(max_length=20, null=True, blank=True)  # Para temas legales/fiscales (opcional)
    legal_name = models.CharField(max_length=200, blank=True)  # Nombre jurídico, si aplica
    is_verified = models.BooleanField(default=False)  # Nuevo campo añadido

    foundation_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    logo = models.ImageField(upload_to=store_logo_upload_path, null=True, blank=True)
    banner = models.ImageField(upload_to=store_banner_upload_path, null=True, blank=True)
    qr_code = models.ImageField(upload_to=store_qr_upload_path, null=True, blank=True)
    
    # Relación muchos a muchos con usuarios administradores
    administrators = models.ManyToManyField(User, related_name='stores')
    first_admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_stores')

    # Ubicación específica de la tienda
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.SET_NULL, null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='stores')
    is_active = models.BooleanField(default=True)

    # Datos analíticos o empresariales
    average_rating = models.FloatField(default=0.0)
    total_visits = models.PositiveIntegerField(default=0)
    location = geomodels.PointField(null=True, blank=True, geography=True)

    def save(self, *args, **kwargs):
            # Si hay un NIT y no está vacío, marcamos como verificada
            if self.nit and self.nit.strip():
                self.verificada = True
            else:
                self.verificada = False
            super().save(*args, **kwargs)
        
    def save(self, *args, **kwargs):
        if not self.slug:
            unique_slug = str(uuid.uuid4())[:20]  # 8 caracteres aleatorios
            while Store.objects.filter(slug=unique_slug).exists():
                unique_slug = str(uuid.uuid4())[:20]
            self.slug = unique_slug
        super().save(*args, **kwargs)
        
        # Generar QR solo si no existe ya (para no regenerar siempre)
        if not self.qr_code:
            qr_url = f"http://localhost:8000/store/{self.slug}/"  # Cambia por tu dominio real
            qr_img = qrcode.make(qr_url)

            # Guardar la imagen en memoria
            canvas = BytesIO()
            qr_img.save(canvas, format='PNG')
            canvas.seek(0)

            # Guardar imagen en campo qr_code
            self.qr_code.save(f'qr_{self.slug}.png', File(canvas), save=False)
            super().save(update_fields=['qr_code'])  # Guarda sólo qr_code
    
    def is_open_now(self):
        now = timezone.localtime()
        day_number = now.weekday() + 1  # 1 = Lunes, ..., 7 = Domingo
        current_time = now.time()

        schedules_today = self.schedules.filter(day=day_number)
        return any(s.open_time <= current_time <= s.close_time for s in schedules_today)

    
    def __str__(self):
        return self.name

class StoreSchedule(models.Model):
    DAY_CHOICES = (
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
        (7, 'Sunday'),
    )

    store = models.ForeignKey(Store, related_name='schedules', on_delete=models.CASCADE)
    day = models.IntegerField(choices=DAY_CHOICES)
    open_time = models.TimeField()
    close_time = models.TimeField()

# Ejemplo Si tengo 1000 productos, pero su subcategoria es 128GB no viola las leyes de la normalizcion    
# Ejemplo:
# ID	name	    parent	    store
# 1	    Apple	    null	    1
# 2	    iPhone X	Apple	    1
# 3	    128GB	    iPhone X	1
# 4	    Samsung	    null	    1
# 5	    Galaxy S9	Samsung	    1
# 6	    128GB	    Galaxy S9	1
# Aunque ambas se llaman "128GB", tienen distintos parent, así que no violan la restricción.

class CategoryProduct(models.Model):
    name = models.CharField(max_length=100)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="categories")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subcategories')

    slug = models.SlugField(unique=True)  # opcional, útil para URLs

    class Meta:
        unique_together = ('name', 'store', 'parent')  # Evita duplicados

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while CategoryProduct.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.store.name})"   
     

class Review(models.Model):
    store = models.ForeignKey('Store', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField()  # Ej: 1 a 5
    comment = models.TextField(blank=True, validators=[MaxLengthValidator(300)])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('store', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.store.name} - {self.user.username} - {self.rating}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_store_average_rating()

    def delete(self, *args, **kwargs):
        store = self.store
        super().delete(*args, **kwargs)
        self.update_store_average_rating(store)

    def update_store_average_rating(self, store=None):
        store = store or self.store
        avg = store.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        store.average_rating = round(avg, 2)
        store.save(update_fields=['average_rating'])

#Las tiendas tienen control total sobre sus zonas y envíos.
#Puede definir zonas amplias (nacionales), medianas (ciudades) o específicas (barrios).
#Cada método de envío puede tener múltiples zonas con precios distintos.
#es perfectamente válido y profesional mover el modelo Review a NoSQL, si el uso principal es mostrar reseñas rápidamente por tienda, sin lógica compleja.

# Flujo de Funcionamiento

# El diseño sigue una lógica clara:

#     ShippingZone: Define áreas geográficas (desde países hasta barrios)

#     ShippingMethod: Define métodos de envío con costos base

#     ShippingMethodZone: Personaliza métodos por zona (patrón bridge)

# Este diseño permite:

#     Definir múltiples métodos de envío por tienda

#     Personalizar costos y tiempos por zona geográfica

#     Escalar fácilmente añadiendo nuevas zonas o métodos

# Envios por localidad
class ShippingZone(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='shipping_zones')
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.SET_NULL, null=True, blank=True)

    def clean(self):
        filters = {
            'store': self.store,
            'country': self.country,
            'city': self.city,
            'neighborhood__isnull': self.neighborhood is None,
        }

        if self.neighborhood:
            filters['neighborhood'] = self.neighborhood

        qs = ShippingZone.objects.filter(**filters)
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        if qs.exists():
            raise ValidationError("Ya existe una zona de envío con esta ubicación para esta tienda.")

    def save(self, *args, **kwargs):
        self.full_clean()  # llama a clean() antes de guardar
        super().save(*args, **kwargs)


class ShippingMethod(models.Model):
    STANDARD = 'standard'
    EXPRESS = 'express'
    SAME_DAY = 'same_day'
    PICKUP = 'pickup'
    HOME_SERVICE = 'home_service'
    IN_STORE = 'in_store'
    DELIVERY_BY_RIDER = 'rider_delivery'
    IN_LINE = 'in_line'
    BY_PHONE='by_phone'


    METHOD_CHOICES = [
        (STANDARD, 'Envío estándar'),         # General
        (EXPRESS, 'Entrega express'),         # General
        (SAME_DAY, 'Entrega el mismo día'),   # General
        (PICKUP, 'Recogida en tienda'),       # Tiendas y restaurantes
        (DELIVERY_BY_RIDER, 'Entrega por repartidor'),  # Restaurantes
        (HOME_SERVICE, 'Servicio a domicilio'),         # Servicios
        (IN_STORE, 'Servicio en el local'),             # Servicios presenciales
        (IN_LINE, 'Servicio en linea'),
        (BY_PHONE, 'Servicio telefónico'),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='shipping_methods')
    name = models.CharField(max_length=100, choices=METHOD_CHOICES)
    description = models.TextField(blank=True)

    base_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    estimated_days = models.PositiveIntegerField(null=True, blank=True, default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.store.name})"
    
class ShippingMethodZone(models.Model):
    shipping_method = models.ForeignKey(ShippingMethod, on_delete=models.CASCADE, related_name='zones')
    zone = models.ForeignKey(ShippingZone, on_delete=models.CASCADE)
    custom_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    custom_days = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('shipping_method', 'zone')

    def __str__(self):
        return f"{self.shipping_method.name} para {self.zone}"


class PaymentMethod(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="payment_methods")
    
    name = models.CharField(max_length=100)  # Ej: "Nequi", "MercadoPago", "CBU Banco Nación"
    account_name = models.CharField(max_length=150, blank=True, null=True)  # Titular de la cuenta
    account_number = models.CharField(max_length=100, blank=True, null=True)  # Número, CBU, alias, etc.
    payment_link = models.URLField(blank=True, null=True)  # Link de pago externo (opcional)
    qr_code = models.ImageField(upload_to=store_qr_pay, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.store.name}"
    

class Coupon(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(choices=[('percentage', 'Percentage'), ('fixed', 'Fixed')], max_length=20)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()


class StoreRaffle(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prize = models.CharField(max_length=200)
    image = models.ImageField(upload_to="raffle_images/", null=True, blank=True)
    active = models.BooleanField(default=True)
    min_purchase = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Monto mínimo
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    def __str__(self):
        return self.title


class Combo(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='combos')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to=combo_image_upload, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ComboItem(models.Model):
    combo = models.ForeignKey(Combo, on_delete=models.CASCADE, related_name='items')
    product_id = models.CharField(max_length=50)  # Mongo ObjectId en texto
    sku = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    selected_options = models.JSONField(default=dict, blank=True)

    def clean(self):
        product = get_product_by_id(self.product_id)
        if not product:
            raise ValidationError("Producto no encontrado en MongoDB.")

        expected_sku = product.get("sku")

        if self.sku is not None and self.sku != expected_sku:
            raise ValidationError(
                f"El SKU no coincide con el producto base. Esperado: {expected_sku}, recibido: {self.sku}"
            )

        if self.selected_options:
            raise ValidationError("selected_options debe estar vacío. No se admiten opciones para combos.")


