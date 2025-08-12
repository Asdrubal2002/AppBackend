from django.db import models
from django.conf import settings
from apps.stores.models import Store, Coupon, StoreRaffle, Combo
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.stores.models import PaymentMethod
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from datetime import timedelta
import secrets
import string
import uuid
from ..mongo_utils import get_product_by_id


def store_payment_proof(instance, filename):
    return f'stores/{instance.store.id}/orders/{instance.id}/proof/{filename}'


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carts")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="carts")

    items_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    notes = models.TextField(blank=True, null=True)
    reserved_until = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def update_totals(self):
        items = self.items.all()

        subtotal = Decimal('0.00')  # lo pagado (con descuentos)
        total = Decimal('0.00')     # el precio original sin descuentos

        for item in items:
            subtotal += item.total_price  # ya con descuentos

            # Excluir productos internos del combo
            if item.combo and item.price == Decimal("0.00"):
                continue

            product = get_product_by_id(item.product_id)
            if not product:
                base_price = item.price  # fallback
            else:
                variants = product.get('variants', [])
                if variants:
                    variant = next((v for v in variants if v.get('sku') == item.sku), None)
                    base_price = Decimal(variant.get('price')) if variant else item.price
                else:
                    base_price = Decimal(product.get('price')) if product.get('price') else item.price

            total += base_price * item.quantity  # precio sin descuento

        self.items_subtotal = subtotal   # lo que realmente paga el usuario
        self.total = total               # precio total original sin descuentos
        self.save()

    def clear_items(self):
        self.items.all().delete()
        self.update_totals()

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())
    
    def __str__(self):
        return f"Cart #{self.pk} - {self.store.name} ({'Active' if self.is_active else 'Closed'})"

    
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product_id = models.CharField(max_length=100)  # Mongo ID como string
    product_name = models.CharField(max_length=255)  # Nombre al momento de agregar al carrito
    sku = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # ← Agrega este campo
    selected_options = models.JSONField(default=dict, blank=True)  # ejemplo: { "Talla": "M", "Color": "Negro" }
    combo = models.ForeignKey(Combo, on_delete=models.SET_NULL, null=True, blank=True, related_name="cart_items")
    combo_instance_id = models.UUIDField(null=True, blank=True, db_index=True) 

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('cart', 'sku', 'combo_instance_id')
        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["sku"]),
        ]

    @property
    def total_price(self):
        return self.price * self.quantity

    def save(self, *args, **kwargs):
        self.full_clean()  # 👈 Ejecuta clean() automáticamente
        super().save(*args, **kwargs)
        self.cart.update_totals()

    def clean(self):
        # ⛔ Saltar validación si el item viene de un combo
        if self.combo:
            return

        from ..mongo_utils import get_product_by_id

        product = get_product_by_id(self.product_id)
        if not product:
            raise ValidationError("Producto no encontrado")

        variants = product.get('variants', [])

        if variants:
            variant = next((v for v in variants if v.get('sku') == self.sku), None)
            if not variant:
                raise ValidationError("Variante no encontrada")

            stock = variant.get('stock', 0)
            if self.quantity > stock:
                raise ValidationError(f"Cantidad ({self.quantity}) supera el stock disponible ({stock})")

            if self.selected_options != variant.get('options', {}):
                raise ValidationError("Las opciones seleccionadas no coinciden con la variante.")
        else:
            if self.sku != product.get('sku'):
                raise ValidationError("SKU inválido para producto sin variantes.")

            stock = product.get('stock', 0)
            if self.quantity > stock:
                raise ValidationError(f"Cantidad ({self.quantity}) supera el stock disponible ({stock})")

            if self.selected_options:
                raise ValidationError("Este producto no tiene variantes ni opciones seleccionables.")


class CheckoutSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    cart = models.OneToOneField(Cart, on_delete=models.CASCADE)

    items_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


def generate_reference():
    return uuid.uuid4().hex[:10].upper()

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('expired', 'Expirada'),
        ('cancelled', 'Cancelada'),
        ('delivered', 'Entregada'),
    ]

    reference = models.CharField(max_length=12, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True)
    
    items_subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    payment_proof = models.ImageField(upload_to=store_payment_proof, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)

    def generate_reference(self):
        return uuid.uuid4().hex[:10].upper()
    

class RaffleEntry(models.Model):
    raffle = models.ForeignKey(StoreRaffle, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)       