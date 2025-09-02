from rest_framework import serializers
from django.utils.timezone import now
from datetime import datetime, date
from ..products import create_product, apply_discount  # Lógica para guardar en MongoDB
from apps.stores.models import Store
import uuid
from apps.stores.models import CategoryProduct

class DateFromMongoField(serializers.DateField):
    def to_representation(self, value):
        if isinstance(value, datetime):
            value = value.date()
        return super().to_representation(value)

class ProductOptionSerializer(serializers.Serializer):
    name = serializers.CharField()
    values = serializers.ListField(child=serializers.CharField())


class ProductSerializer(serializers.Serializer):
    _id = serializers.CharField(read_only=True)
    store_id = serializers.IntegerField()
    category = serializers.IntegerField(required=False, allow_null=True)
    category_name = serializers.SerializerMethodField()
    store_category = serializers.IntegerField(read_only=True)

    # Información básica
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, max_length=500)
    price = serializers.FloatField(min_value=0)
    stock = serializers.IntegerField(min_value=0, default=0)
    is_active = serializers.BooleanField(default=True)

    # Descuentos
    discount_percentage = serializers.FloatField(
        required=False, min_value=0, max_value=100
    )
    discount_start = DateFromMongoField(required=False, format="%Y-%m-%d")
    discount_end = DateFromMongoField(required=False, format="%Y-%m-%d")

    # Especificaciones generales
    brand = serializers.CharField(required=False, allow_blank=True, max_length=100)
    model = serializers.CharField(required=False, allow_blank=True, max_length=100)
    specifications = serializers.DictField(
        child=serializers.CharField(), required=False, allow_empty=True
    )

    # Garantía y estado
    warranty = serializers.CharField(required=False, allow_blank=True, max_length=100)
    condition = serializers.ChoiceField(choices=["Nuevo", "Usado"], default="Nuevo")

    # Medidas y peso
    weight_kg = serializers.FloatField(required=False, allow_null=True)
    dimensions_cm = serializers.DictField(
        child=serializers.FloatField(), required=False, allow_empty=True
    )

    # Envío
    shipping_included = serializers.BooleanField(default=False)

    # Identificación interna
    sku = serializers.CharField(required=False, allow_blank=True, max_length=100)
    barcode = serializers.CharField(required=False, allow_blank=True, max_length=100)

    # SEO y otros
    slug = serializers.SlugField(required=False, allow_blank=True)
    keywords = serializers.ListField(
        child=serializers.CharField(max_length=50), required=False, allow_empty=True
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50), required=False, allow_empty=True
    )

    # Métricas (solo lectura)
    likes = serializers.IntegerField(read_only=True, default=0)
    dislikes = serializers.IntegerField(read_only=True, default=0)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    average_rating = serializers.FloatField(read_only=True, default=0.0)
    views_count = serializers.IntegerField(read_only=True, default=0)
    sold_count = serializers.IntegerField(read_only=True, default=0)

    #Media del producto
    media = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    # Control
    is_featured = serializers.BooleanField(default=False)
    is_recommended = serializers.BooleanField(default=False)
    visibility = serializers.ChoiceField(
        choices=["publico", "privado", "tienda"], default="publico"
    )

    # Timestamp
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    # Datos embebidos
    store_name = serializers.SerializerMethodField()
    store_logo = serializers.SerializerMethodField()
    store_slug = serializers.SerializerMethodField()
    country_id = serializers.IntegerField(read_only=True)
    city_id = serializers.IntegerField(read_only=True)
    neighborhood_id = serializers.IntegerField(read_only=True)

    store_latitude  = serializers.SerializerMethodField()
    store_longitude = serializers.SerializerMethodField()


    # Opciones del producto (e.g., Talla, Color)
    options = serializers.ListField(
        child=ProductOptionSerializer(),
        required=False,
        default=list
    )

    # Variantes concretas del producto
    variants = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text="Ej: [{'sku': '1234-S-ROJO', 'price': 10000, 'stock': 10, 'options': {'Talla': 'S', 'Color': 'Rojo'}}]"
    )
    
    # GETS embebidos
    def get_store_name(self, obj):
        return obj.get("store", {}).get("name", "") or obj.get("store_name", "")

    def get_store_logo(self, obj):
        return obj.get("store", {}).get("logo", "") or obj.get("store_logo_url", "")

    def get_store_slug(self, obj):
        return obj.get("store", {}).get("slug", "") or obj.get("store_slug", "")

    # coordenadas
    def get_store_latitude(self, obj):
        loc = obj.get("store", {}).get("location")
        return loc["coordinates"][1] if loc else None   # lat

    def get_store_longitude(self, obj):
        loc = obj.get("store", {}).get("location")
        return loc["coordinates"][0] if loc else None   # lon


    def get_discount_start_date(self, obj):
        val = obj.get('discount_start')
        if isinstance(val, datetime):
            return val.date()
        return val

    def get_discount_end_date(self, obj):
        val = obj.get('discount_end')
        if isinstance(val, datetime):
            return val.date()
        return val

    def get_category_name(self, obj):
            category_id = obj.get('category')
            if category_id:
                try:
                    category = CategoryProduct.objects.get(id=category_id)
                    return category.name
                except CategoryProduct.DoesNotExist:
                    return None
            return None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['_id'] = str(instance.get('_id'))

        # Datos de descuento
        discount = instance.get('discount_percentage')
        start = instance.get('discount_start')
        end = instance.get('discount_end')
        today = date.today()

        # Precio con descuento
        ret['discounted_price'] = apply_discount(
            instance.get('price'), discount, start, end, today
        )

        # Precio con descuento para cada variante
        if 'variants' in ret:
            for idx, variant in enumerate(ret['variants']):
                price = variant.get('price')
                if price is not None:
                    ret['variants'][idx]['discounted_price'] = apply_discount(
                        price, discount, start, end, today
                    )

        return ret

    
    def validate(self, data):
        # Validar fechas de descuento
        start = data.get('discount_start')
        end = data.get('discount_end')
        percentage = data.get('discount_percentage')

        # Si hay fecha de fin, debe haber fecha de inicio
        if end and not start:
            raise serializers.ValidationError("Debes especificar la fecha de inicio del descuento.")

        # Validar fechas coherentes
        if start and end and start > end:
            raise serializers.ValidationError("La fecha de inicio del descuento no puede ser posterior a la fecha de fin.")

        # Si hay porcentaje, validar que tenga al menos una fecha
        if percentage is not None and (not start or not end):
            raise serializers.ValidationError("Para aplicar un descuento se requieren las fechas de inicio y fin.")

        # Validar que si hay fechas, haya porcentaje
        if (start or end) and percentage is None:
            raise serializers.ValidationError("Para establecer un descuento debes indicar el porcentaje.")


        options = data.get("options", [])
        variants = data.get("variants", [])

        option_map = {}

        # Validar las opciones definidas por el producto
        for opt in options:
            name = opt.get("name")
            values = opt.get("values", [])

            if not name or not isinstance(name, str):
                raise serializers.ValidationError("Cada opción debe tener un 'name' válido (string no vacío).")

            if not isinstance(values, list) or not values:
                raise serializers.ValidationError(f"La opción '{name}' debe tener una lista de 'values' no vacía.")

            if len(set(values)) != len(values):
                raise serializers.ValidationError(f"La opción '{name}' contiene valores duplicados.")

            if name in option_map:
                raise serializers.ValidationError(f"La opción '{name}' está duplicada.")

            option_map[name] = values

        # Validar variantes
        seen_variants = set()

        for index, variant in enumerate(variants):
            sku = variant.get("sku", f"índice {index}")
            variant_options = variant.get("options")

            if not sku:
                raise serializers.ValidationError(f"La variante en el índice {index} no tiene 'sku'.")

            if not isinstance(variant_options, dict):
                raise serializers.ValidationError(f"Variante '{sku}' debe tener un objeto 'options' válido.")

            # Validar que tenga todas las opciones requeridas
            for required_option in option_map:
                if required_option not in variant_options:
                    raise serializers.ValidationError(
                        f"Variante '{sku}': falta la opción obligatoria '{required_option}'."
                    )

            # Validar que no tenga opciones extra
            for key, val in variant_options.items():
                if key not in option_map:
                    raise serializers.ValidationError(
                        f"Variante '{sku}': opción inválida '{key}' no está definida en las options del producto."
                    )
                if val not in option_map[key]:
                    raise serializers.ValidationError(
                        f"Variante '{sku}': valor inválido '{val}' para la opción '{key}'. "
                        f"Valores permitidos: {option_map[key]}"
                    )

            # Validar duplicados
            option_signature = tuple(sorted(variant_options.items()))
            if option_signature in seen_variants:
                raise serializers.ValidationError(
                    f"La variante '{sku}' está duplicada: misma combinación de opciones que otra variante."
                )
            seen_variants.add(option_signature)

        return data

    def create(self, validated_data):
        store_id = validated_data.get("store_id")
        product_price = validated_data.get("price")
        variants = validated_data.get("variants", [])

        # Reemplazar precios nulos o cero
        for variant in variants:
            # Generar SKU si no se proporciona
            if not variant.get("sku"):
                unique_id = uuid.uuid4().hex[:6].upper()
                name_fragment = validated_data.get("name", "PROD")[:3].upper()
                variant["sku"] = f"{name_fragment}-{unique_id}"

            # Usar precio global si la variante no lo tiene
            price = variant.get("price")
            if price in [None, '', 0]:
                variant["price"] = product_price

        # Actualizar stock global y precio global basado en variantes
        if variants:
            validated_data["stock"] = sum(v.get("stock", 0) for v in variants)

            # Usamos el precio menor de las variantes
            validated_data["price"] = min(
                (v.get("price") for v in variants if v.get("price") not in [None, '', 0]),
                default=product_price
            )


        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            raise serializers.ValidationError("Tienda no encontrada")

        validated_data["store_category"] = store.category.id if store.category else None
        lat = store.location.y if store.location else None
        lon = store.location.x if store.location else None

        location_data = None
        if store.location and store.location.x is not None and store.location.y is not None:
            location_data = {
                "type": "Point",
                "coordinates": [store.location.x, store.location.y]
            }

        validated_data["store"] = {
            "name": store.name,
            "logo": store.logo.url if store.logo else "",
            "slug": store.slug,
        }

        if location_data:
            validated_data["store"]["location"] = location_data

        validated_data["country_id"] = store.country.id if store.country else None
        validated_data["city_id"] = store.city.id if store.city else None
        validated_data["neighborhood_id"] = store.neighborhood.id if store.neighborhood else None

        now = datetime.utcnow()
        validated_data["created_at"] = now
        validated_data["updated_at"] = now

        # Validación de stock
        if not variants:
            if not validated_data.get("stock") or validated_data["stock"] <= 0:
                raise serializers.ValidationError("Debes ingresar un stock si el producto no tiene variantes.")
        else:
            for variant in variants:
                if not variant.get("stock") or variant["stock"] <= 0:
                    raise serializers.ValidationError("Todas las variantes deben tener stock mayor a 0.")

        # Generar SKU del producto si está vacío y no hay variantes
        if not validated_data.get("sku"):
            name_fragment = validated_data.get("name", "PROD")[:3].upper()
            unique_id = uuid.uuid4().hex[:6].upper()
            validated_data["sku"] = f"{name_fragment}-{unique_id}"

        return create_product(validated_data)

    # UPDATE
    def update(self, instance, validated_data):
        from ..products import update_product, get_product
        update_product(str(instance["_id"]), validated_data)
        return get_product(str(instance["_id"]))