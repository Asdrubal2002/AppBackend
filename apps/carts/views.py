from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from bson import ObjectId
from .models import Cart, CartItem, CheckoutSession, Order, Combo
from .serializers import CartSerializer, CheckoutSessionSerializer, OrderSerializer, OrderDetailSerializer
from ..mongo_utils import get_product_by_id
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from mongo_client.models.product.products import apply_discount
import sys
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError
from apps.stores.models import (Coupon, 
                                ShippingMethod,
                                 PaymentMethod, 
                                 ShippingZone, 
                                 ShippingMethodZone,
                                 ) 
from django.db import transaction
from django.utils.crypto import get_random_string
from django.db.models import Q
from django.utils import timezone
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from datetime import timedelta
import uuid

User = get_user_model()

def force_log(*args):
    sys.stderr.write(" ".join(str(a) for a in args) + "\n")
    sys.stderr.flush()

def safe_decimal(value):
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except:
        return Decimal('0.00')


class CartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        force_log("⚡ ENTRÓ A CartAPIView ⚡ con: {store_id}, {product_id},{sku}")

        user = request.user
        data = request.data
        required_fields = ['store_id', 'product_id', 'sku', 'quantity']
        for field in required_fields:
            if field not in data:
                return Response({"error": f"{field} is required."}, status=400)

        product = get_product_by_id(data['product_id'])
        if not product:
            return Response({"error": "Product not found."}, status=404)

        if product.get('store_id') != data['store_id']:
            return Response({"error": "Product does not belong to the store."}, status=400)

        variants = product.get('variants', [])
        quantity = int(data['quantity'])

        if variants:
            variant = next((v for v in variants if v.get('sku') == data['sku']), None)
            if not variant:
                return Response({"error": "Variant not found."}, status=404)

            stock = variant.get('stock', 0)
            selected_options = variant.get('options', {})
            base_price = safe_decimal(variant.get('price'))
            discounted_price = safe_decimal(variant.get('discounted_price'))
        else:
            if data['sku'] != product.get('sku'):
                return Response({"error": "Invalid SKU for product without variants."}, status=400)

            variant = None
            stock = product.get('stock', 0)
            selected_options = {}
            base_price = safe_decimal(product.get('price'))
            discounted_price = safe_decimal(product.get('discounted_price'))

        if stock < quantity:
            return Response({"error": "Insufficient stock."}, status=400)

    
        # 🧮 Calcular si aplica descuento
        today = date.today()
        discount_start = product.get('discount_start')
        discount_end = product.get('discount_end')
        discount_percentage = safe_decimal(product.get('discount_percentage'))
        use_discount = False

        try:
            if isinstance(discount_start, str):
                discount_start = date.fromisoformat(discount_start)
            elif isinstance(discount_start, datetime):
                discount_start = discount_start.date()

            if isinstance(discount_end, str):
                discount_end = date.fromisoformat(discount_end)
            elif isinstance(discount_end, datetime):
                discount_end = discount_end.date()

            if discount_start and discount_end:
                use_discount = discount_start <= today <= discount_end
        except Exception as e:
            force_log("❌ Error parsing fechas:", e)

        # 💰 Determinar precio final
        if discounted_price <= 0 and use_discount and discount_percentage > 0:
            discounted_price = base_price * (Decimal('1.0') - discount_percentage / 100)

        if use_discount and discounted_price > 0 and discounted_price < base_price:
            current_price = discounted_price
        else:
            current_price = base_price

        # 🛒 Crear o actualizar carrito
        cart, _ = Cart.objects.get_or_create(
            user=user,
            store_id=data['store_id'],
            is_active=True,
        )

        cart.save()
        cart.update_totals()

        # 🧾 Nombre del producto
        product_name = product.get('name', '')

        # 🚫 Eliminar ítem anterior si ya existe
        CartItem.objects.filter(
            cart=cart,
            sku=data['sku'],
            combo_instance_id__isnull=True  # ✅ Solo productos individuales
        ).delete()

        force_log(f"💵 current_price sin redondear: {current_price}")
        # ✅ Crear ítem nuevo
        CartItem.objects.create(
            cart=cart,
            product_id=data['product_id'],
            product_name=product_name,
            sku=data['sku'],
            quantity=quantity,
            selected_options=selected_options,
            price=current_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )

        force_log("✅ Carrito actualizado correctamente")

        return Response(CartSerializer(cart, context={'request': request}).data, status=200)

class UserCartListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        carts = Cart.objects.filter(user=request.user, is_active=True)\
            .select_related('store')\
            .prefetch_related('items')

        serializer = CartSerializer(carts, many=True, context={'request': request})
        return Response(serializer.data, status=200)
    
class UserCartDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        cart = get_object_or_404(Cart, pk=pk, user=request.user, is_active=True)
        serializer = CartSerializer(cart, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        cart = get_object_or_404(Cart, pk=pk, user=request.user, is_active=True)
        cart.is_active = False
        cart.save()
        return Response({"detail": "Canasta eliminada correctamente."}, status=status.HTTP_200_OK)
    
class UpdateCartItemQuantityAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        required_fields = ['store_id', 'product_id', 'sku', 'action']
        for field in required_fields:
            if field not in data:
                return Response({"error": f"{field} is required."}, status=400)

        action = data['action']
        if action not in ['increment', 'decrement', 'set_quantity']:
            return Response({"error": "Invalid action."}, status=400)

        combo_instance_id = data.get('combo_instance_id')

        try:
            cart = Cart.objects.get(user=user, store_id=data['store_id'], is_active=True)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found."}, status=404)

        try:
            filters = {
                "cart": cart,
                "sku": data['sku'],
                "combo_instance_id__isnull": combo_instance_id is None
            }
            if combo_instance_id:
                filters["combo_instance_id"] = combo_instance_id

            cart_item = CartItem.objects.get(**filters)

        except CartItem.DoesNotExist:
            return Response({"error": "Item not found in cart."}, status=404)
        except CartItem.MultipleObjectsReturned:
            return Response({"error": "Multiple items found. combo_instance_id is required to disambiguate."}, status=400)

        is_combo_main = str(data['product_id']).startswith("combo-")

        if is_combo_main and combo_instance_id:
            combo_items = cart.items.filter(combo_instance_id=combo_instance_id)
            combo_main = combo_items.filter(sku=data['sku']).first()

            if not combo_main:
                return Response({"error": "Combo principal no encontrado."}, status=404)

            quantity = combo_main.quantity
            if action == 'increment':
                new_quantity = quantity + 1
            elif action == 'decrement':
                new_quantity = quantity - 1
            elif action == 'set_quantity':
                if 'quantity' not in data:
                    return Response({"error": "'quantity' is required for 'set_quantity' action."}, status=400)
                new_quantity = int(data['quantity'])

            if new_quantity < 1:
                combo_items.delete()
                cart.update_totals()
                return Response(CartSerializer(cart, context={'request': request}).data, status=200)

            for item in combo_items.exclude(sku=data['sku']):
                product = get_product_by_id(item.product_id)
                if not product:
                    return Response({"error": f"Producto '{item.product_id}' no encontrado."}, status=404)

                if product.get("variants"):
                    variant = next((v for v in product["variants"] if v["sku"] == item.sku), None)
                    if not variant:
                        return Response({"error": f"Variante inválida '{item.sku}'."}, status=404)
                    stock = variant.get("stock", 0)
                else:
                    stock = product.get("stock", 0)

                base_qty = item.quantity // quantity
                if base_qty * new_quantity > stock:
                    return Response({"error": f"Stock insuficiente para '{product.get('name')}'"}, status=400)

            for item in combo_items:
                if item.sku == data['sku']:
                    item.quantity = new_quantity
                else:
                    base_qty = item.quantity // quantity
                    item.quantity = base_qty * new_quantity
                item.save()

            cart.update_totals()
            return Response(CartSerializer(cart, context={'request': request}).data, status=200)

        # --- Producto individual ---
        product = get_product_by_id(data['product_id'])
        if not product:
            return Response({"error": "Product not found."}, status=404)

        variants = product.get('variants', [])
        quantity = cart_item.quantity

        if variants:
            variant = next((v for v in variants if v.get('sku') == data['sku']), None)
            if not variant:
                return Response({"error": "Variant not found."}, status=404)
            stock = variant.get('stock', 0)
        else:
            if product.get('sku') != data['sku']:
                return Response({"error": "Invalid SKU for product without variants."}, status=400)
            stock = product.get('stock', 0)

        if action == 'increment':
            if quantity + 1 > stock:
                return Response({"error": "Insufficient stock."}, status=400)
            cart_item.quantity += 1

        elif action == 'decrement':
            if quantity <= 1:
                cart_item.delete()
                cart.update_totals()
                return Response(CartSerializer(cart, context={'request': request}).data, status=200)
            cart_item.quantity -= 1

        elif action == 'set_quantity':
            if 'quantity' not in data:
                return Response({"error": "'quantity' is required for 'set_quantity' action."}, status=400)
            new_quantity = int(data['quantity'])
            if new_quantity < 1:
                cart_item.delete()
                cart.update_totals()
                return Response(CartSerializer(cart, context={'request': request}).data, status=200)
            if new_quantity > stock:
                return Response({"error": "Insufficient stock."}, status=400)
            cart_item.quantity = new_quantity

        cart_item.full_clean()
        cart_item.save()
        cart.update_totals()
        return Response(CartSerializer(cart, context={'request': request}).data, status=200)

class DeleteCartItemAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        required_fields = ['store_id', 'sku']
        for field in required_fields:
            if field not in data:
                return Response({"error": f"{field} is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart = Cart.objects.get(user=user, store_id=data['store_id'], is_active=True)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            combo_instance_id = data.get('combo_instance_id')
            filters = {
                "cart": cart,
                "sku": data['sku'],
                "combo_instance_id__isnull": combo_instance_id is None
            }
            if combo_instance_id:
                filters["combo_instance_id"] = combo_instance_id

            cart_item = CartItem.objects.get(**filters)

        except CartItem.DoesNotExist:
            return Response({"error": "Item not found in cart."}, status=status.HTTP_404_NOT_FOUND)
        except CartItem.MultipleObjectsReturned:
            return Response({"error": "Multiple items found. combo_instance_id is required."}, status=400)

        if cart_item.combo and cart_item.sku.startswith("COMBO-") and cart_item.combo_instance_id:
            CartItem.objects.filter(cart=cart, combo_instance_id=cart_item.combo_instance_id).delete()
        else:
            cart_item.delete()

        cart.update_totals()

        if cart.items.count() == 0:
            return Response({"cart": None}, status=status.HTTP_200_OK)

        return Response({"cart": CartSerializer(cart, context={'request': request}).data}, status=status.HTTP_200_OK)

class CheckoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        cart_id = data.get("cart_id")
        coupon_code = data.get("coupon_code", "").strip()
        shipping_method_id = data.get("shipping_method_id")

        if not shipping_method_id:
            return Response({"error": "shipping_method_id is required."}, status=400)

        # 🛒 Validar carrito
        try:
            cart = Cart.objects.get(id=cart_id, user=user, is_active=True)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found."}, status=404)

        items_subtotal = cart.items_subtotal

        
      
        # 📍 Determinar zona de envío del usuario
        def get_best_shipping_zone(user, store):
            if user.neighborhood:
                zone = ShippingZone.objects.filter(store=store, neighborhood=user.neighborhood).first()
                if zone:
                    return zone
            if user.city:
                zone = ShippingZone.objects.filter(store=store, city=user.city, neighborhood__isnull=True).first()
                if zone:
                    return zone
            if user.country:
                zone = ShippingZone.objects.filter(
                    store=store,
                    country=user.country,
                    city__isnull=True,
                    neighborhood__isnull=True
                ).first()
                if zone:
                    return zone
            return None

        shipping_cost = Decimal("0.00")
        # 📍 Determinar zona de envío del usuario
        zone = get_best_shipping_zone(user=user, store=cart.store)
        if not zone:
            return Response({"error": "No shipping zone found for your location."}, status=400)

        # 🚚 Validar método de envío para la zona
        try:
            smz = ShippingMethodZone.objects.select_related("shipping_method").get(
                shipping_method_id=shipping_method_id,
                zone=zone,
                shipping_method__is_active=True
            )
        except ShippingMethodZone.DoesNotExist:
            return Response({"error": "Shipping method is not available in your location."}, status=400)

        shipping_method = smz.shipping_method
        shipping_cost = smz.custom_cost if smz.custom_cost is not None else shipping_method.base_cost or Decimal("0.00")


        if zone:
            method_zone = ShippingMethodZone.objects.filter(
                shipping_method=shipping_method,
                zone=zone
            ).first()

            if method_zone and method_zone.custom_cost is not None:
                shipping_cost = method_zone.custom_cost
            else:
                shipping_cost = shipping_method.base_cost or Decimal("0.00")
        else:
            shipping_cost = shipping_method.base_cost or Decimal("0.00")

        # 💸 Validar cupón
        discount_total = Decimal("0.00")
        coupon = None
        warning = None

        if coupon_code:
            now = timezone.now()
            try:
                candidate_coupon = Coupon.objects.get(
                    code__iexact=coupon_code,
                    store=cart.store,
                    active=True,
                    valid_from__lte=now,
                    valid_to__gte=now
                )
                if candidate_coupon.usage_limit and candidate_coupon.used_count >= candidate_coupon.usage_limit:
                    warning = "Coupon usage limit reached. Proceeding without discount."
                else:
                    coupon = candidate_coupon
                    if coupon.discount_type == "percentage":
                        discount_total = (items_subtotal * coupon.value / 100).quantize(Decimal("0.01"))
                    elif coupon.discount_type == "fixed":
                        discount_total = min(coupon.value, items_subtotal)
            except Coupon.DoesNotExist:
                warning = "Coupon not found or invalid. Proceeding without discount."
               
        # Calcular total
        total = items_subtotal + shipping_cost - discount_total

        # Crear sesión de checkout
        session = CheckoutSession.objects.create(
            user=user,
            store=cart.store,
            cart=cart,
            items_subtotal=items_subtotal,
            shipping_cost=shipping_cost,
            discount_total=discount_total,
            total=total,
            coupon=coupon
        )

        response_data = CheckoutSessionSerializer(session).data
        if warning:
            response_data["warning"] = warning

        return Response(response_data, status=201)

class CreateOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data
        checkout_id = data.get("checkout_session_id")
        payment_method_id = data.get("payment_method_id")
        notes = data.get("notes", "")

        try:
            session = CheckoutSession.objects.get(id=checkout_id, user=user)
        except CheckoutSession.DoesNotExist:
            return Response({"error": "Checkout session not found."}, status=404)

        if Order.objects.filter(cart=session.cart, status__in=['pending', 'paid']).exists():
            return Response({"error": "Order already exists for this cart."}, status=400)

        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id, store=session.store, is_active=True)
        except PaymentMethod.DoesNotExist:
            return Response({"error": "Invalid payment method."}, status=400)

        expires_at = timezone.now() + timedelta(hours=2)

        order = Order.objects.create(
            user=user,
            store=session.store,
            cart=session.cart,
            payment_method=payment_method,
            items_subtotal=session.items_subtotal,
            shipping_cost=session.shipping_cost,
            discount_total=session.discount_total,
            total=session.total,
            coupon=session.coupon,
            notes=notes,
            expires_at=expires_at,
        )

        # ✅ Desactivar el carrito
        session.cart.is_active = False
        session.cart.save(update_fields=["is_active"])

        # ✅ Marcar cupón como usado si aplica
        if session.coupon:
            session.coupon.used_count += 1
            session.coupon.save(update_fields=["used_count"])

        return Response({
            "message": "Order created.",
            "order_id": order.id,
            "reference": order.reference,
            "total": order.total
        }, status=201)
    
class UploadPaymentProofAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, order_id):
        user = request.user
        try:
            order = Order.objects.get(id=order_id, user=user)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=404)

        if order.expires_at and timezone.now() > order.expires_at:
            return Response({"error": "This payment reference has expired."}, status=400)

        proof = request.FILES.get("payment_proof")
        if not proof:
            return Response({"error": "No file uploaded."}, status=400)

        order.payment_proof = proof
        order.save()
        return Response({"message": "Payment proof uploaded successfully."}, status=200)

class UserOrdersListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        orders = Order.objects.filter(user=user).order_by('-created_at')

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)
    
class StoreOrdersAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, store_id):
        user = request.user

        # Valida que el usuario administre esta tienda
        if not user.stores.filter(id=store_id).exists():
            return Response({"error": "No tienes permiso para ver esta tienda."}, status=403)

        orders = Order.objects.filter(store_id=store_id).order_by('-created_at')
        serializer = OrderDetailSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)

class OrderAdminDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        user = request.user
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Orden no encontrada."}, status=404)

        if not user.stores.filter(id=order.store_id).exists():
            return Response({"error": "No tienes permiso para esta orden."}, status=403)

        serializer = OrderDetailSerializer(order, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, order_id):
        user = request.user
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"error": "Orden no encontrada."}, status=404)

        if not user.stores.filter(id=order.store_id).exists():
            return Response({"error": "No tienes permiso para esta orden."}, status=403)

        new_status = request.data.get('status')
        if new_status not in ['pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled']:
            return Response({"error": "Estado inválido."}, status=400)

        order.status = new_status
        if new_status != "pending":
            order.expires_at = None  # Limpiar expiración si ya cambió estado
        order.save()

        return Response({"success": "Estado actualizado correctamente."})
    
class AddComboToCartAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        combo_id = data.get("combo_id")
        quantity = int(data.get("quantity", 1))
        selected_skus = data.get("skus", {})

        if not combo_id:
            return Response({"error": "combo_id is required."}, status=400)

        combo = get_object_or_404(Combo, id=combo_id, is_active=True)
        store = combo.store

        cart, _ = Cart.objects.get_or_create(user=user, store=store, is_active=True)

        # 🆔 Genera un ID único para esta instancia del combo
        combo_instance_id = uuid.uuid4()

        for item in combo.items.all():
            product_id = str(item.product_id)
            product = get_product_by_id(product_id)
            if not product:
                return Response({"error": f"Producto con ID {product_id} no encontrado."}, status=400)

            has_variants = bool(product.get("variants"))

            sku = selected_skus.get(product_id)
            if has_variants:
                if not sku:
                    return Response({"error": f"Debes seleccionar una variante (sku) para el producto '{product.get('name')}'"}, status=400)

                variant = next((v for v in product.get("variants", []) if v.get("sku") == sku), None)
                if not variant:
                    return Response({"error": f"SKU inválido '{sku}' para el producto '{product.get('name')}'"}, status=400)

                selected_options = variant.get("options", {})
            else:
                sku = product.get("sku")
                selected_options = {}

            CartItem.objects.create(
                cart=cart,
                product_id=product_id,
                product_name=f"{combo.name} - {product.get('name')}",
                sku=sku,
                quantity=item.quantity * quantity,
                price=Decimal("0.00"),
                selected_options=selected_options,
                combo=combo,
                combo_instance_id=combo_instance_id
            )

        # 🎯 Item resumen del combo
        CartItem.objects.create(
            cart=cart,
            product_id=f"combo-{combo.id}",
            product_name=combo.name,
            sku=f"COMBO-{combo.id}-{combo_instance_id}",  # SKU único
            quantity=quantity,
            price=combo.price,
            selected_options={},
            combo=combo,
            combo_instance_id=combo_instance_id
        )

        cart.update_totals()
        return Response(CartSerializer(cart, context={'request': request}).data, status=200)