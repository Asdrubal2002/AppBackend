from rest_framework import serializers
from .models import Cart, CartItem, CheckoutSession, Order
from ..mongo_utils import get_product_by_id
from apps.stores.serializers import StoreSerializer
from apps.stores.models import Combo

class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    variant_details = serializers.SerializerMethodField()
    combo_instance_id = serializers.UUIDField(required=False, allow_null=True) 

    class Meta:
        model = CartItem
        fields = [
            'product_id', 'sku', 'quantity', 'selected_options',
            'price', 'total_price', 'product_name', 'product_image',
            'variant_details', 'combo_instance_id' 
        ]

    def get_combo_object(self, obj):
        try:
            combo_id = int(str(obj.product_id).replace("combo-", ""))
            return Combo.objects.get(id=combo_id)
        except (ValueError, Combo.DoesNotExist):
            return None

    def get_product_name(self, obj):
        if str(obj.product_id).startswith("combo-"):
            combo = self.get_combo_object(obj)
            return combo.name if combo else obj.product_name
        product = get_product_by_id(obj.product_id)
        return product.get('name') if product else obj.product_name

    def get_product_image(self, obj):
        if str(obj.product_id).startswith("combo-"):
            combo = self.get_combo_object(obj)
            request = self.context.get('request')
            if combo and combo.image and request:
                return request.build_absolute_uri(combo.image.url)
            return None
        product = get_product_by_id(obj.product_id)
        request = self.context.get('request')
        if not product:
            return None
        media_items = product.get("media", [])
        for media in media_items:
            if media.get("type") == "image":
                url = media.get("url", "")
                if url.startswith("/"):
                    return request.build_absolute_uri(url)
                return url
        return None

    def get_variant_details(self, obj):
        if str(obj.product_id).startswith("combo-"):
            return None
        product = get_product_by_id(obj.product_id)
        if not product:
            return None
        for variant in product.get('variants', []):
            if variant.get('sku') == obj.sku:
                return {
                    'options': variant.get('options', {}),
                    'stock': variant.get('stock', 0),
                }
        return None

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    store_name = serializers.CharField(source='store.name', read_only=True)
    store_slug = serializers.CharField(source='store.slug', read_only=True)
    store_logo = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id', 'store', 'store_name', 'store_slug','store_logo',
            'items_subtotal', 'total', 'items', 'created_at', 'updated_at'
        ]

    def get_store_logo(self, obj):
        logo = obj.store.logo
        if not logo or not hasattr(logo, 'url'):
            return None
            
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(logo.url)
        return logo.url  # URL relativa si no hay request

class CheckoutSessionSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)

    class Meta:
        model = CheckoutSession
        fields = [
            'id', 'store', 'store_name', 'cart', 'items_subtotal',
            'shipping_cost', 'discount_total', 'total',
            'coupon', 'coupon_code', 'created_at'
        ]

class OrderSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'reference', 'store', 'store_name', 'cart', 'payment_method',
            'payment_method_name', 'items_subtotal', 'shipping_cost', 'discount_total',
            'total', 'status', 'coupon_code', 'notes', 'expires_at', 'created_at'
        ]

class OrderDetailSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)
    payment_method_name = serializers.CharField(source='payment_method.name', read_only=True)
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)
    cart_data = CartSerializer(source="cart", read_only=True)
    payment_proof_url = serializers.SerializerMethodField()

    # Campos del usuario
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_cellphone = serializers.CharField(source='user.cellphone', read_only=True)
    user_address = serializers.CharField(source='user.address', read_only=True)
    user_country = serializers.CharField(source='user.country.name', read_only=True)
    user_city = serializers.CharField(source='user.city.name', read_only=True)
    user_neighborhood = serializers.CharField(source='user.neighborhood.name', read_only=True)


    class Meta:
        model = Order
        fields = [
            'id', 'reference', 'store', 'store_name', 'cart_data', 'payment_method',
            'payment_method_name', 'items_subtotal', 'shipping_cost', 'discount_total',
            'total', 'status', 'coupon_code', 'notes', 'payment_proof_url',
            'expires_at', 'created_at',

            # Datos del usuario
            'user_name', 'user_last_name','user_cellphone',
            'user_address', 'user_country', 'user_city', 'user_neighborhood',
        ]

    def get_payment_proof_url(self, obj):
        request = self.context.get('request')
        if obj.payment_proof and hasattr(obj.payment_proof, 'url'):
            return request.build_absolute_uri(obj.payment_proof.url)
        return None
    
   