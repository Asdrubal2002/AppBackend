from rest_framework import serializers
from .models import (Store, 
                     ShippingZone,
                     ShippingMethod,
                     ShippingMethodZone,
                     Review, 
                     Category, 
                     CategoryProduct, 
                     StoreSchedule, 
                     PaymentMethod,
                     Combo,
                     ComboItem,
                     Coupon
                     )
from apps.locations.models import Country, City, Neighborhood
from django.conf import settings
from apps.users.models import User
from django.core.validators import MaxLengthValidator
from django.contrib.gis.geos import Point
from ..mongo_utils import get_product_by_id

class StoreScheduleSerializer(serializers.ModelSerializer):
    day_display = serializers.SerializerMethodField()

    class Meta:
        model = StoreSchedule
        fields = ['id', 'day', 'open_time', 'close_time', 'day_display']

    def get_day_display(self, obj):
        return obj.get_day_display()

#Esta vista permite que un usuario autenticado cree una tienda y se asigne automáticamente como administrador.
class StoreSerializerCreate(serializers.ModelSerializer):
    schedules = StoreScheduleSerializer(many=True, required=False)
    
    class Meta:
        model = Store
        fields = '__all__'
        read_only_fields = ['slug', 'average_rating', 'total_visits', 'created_at', 'updated_at','administrators']

    def create(self, validated_data):
        schedules_data = validated_data.pop('schedules', [])
        store = Store.objects.create(**validated_data)

        # Crear los horarios
        for schedule in schedules_data:
            StoreSchedule.objects.create(store=store, **schedule)

        # El administrador se asignará manualmente en la vista como ya haces
        return store

#Esta vista permite obtener los filtros de las stores registradas.
class StoreMinimalSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    description = serializers.SerializerMethodField()
    city_name = serializers.CharField(source='city.name', read_only=True) 
    logo = serializers.SerializerMethodField()  


    class Meta:
        model = Store
        fields = ['id', 'name', 'description', 'category_name','logo','slug','is_verified','city_name','average_rating']
        
    def get_description(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 30 else obj.description

    def get_logo(self, obj):
            if obj.logo and hasattr(obj.logo, 'url'):  # Verifica si existe el archivo
                return obj.logo.url  # Devuelve la ruta relativa
            return None  # O una ruta por defecto como '/media/default-store-logo.jpg'

class StoreGeoSerializer(StoreMinimalSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()

    class Meta(StoreMinimalSerializer.Meta):
        fields = StoreMinimalSerializer.Meta.fields + ['latitude', 'longitude', 'distance']

    def get_latitude(self, obj):
        return obj.location.y if obj.location else None

    def get_longitude(self, obj):
        return obj.location.x if obj.location else None

    def get_distance(self, obj):
        if hasattr(obj, 'distance') and obj.distance:
            return round(obj.distance.m)
        return None

#Obtener Store
class StoreSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)  
    country_name = serializers.CharField(source='country.name', read_only=True) 
    city_name = serializers.CharField(source='city.name', read_only=True) 
    neighborhood_name = serializers.CharField(source='neighborhood.name', read_only=True)
    schedules = StoreScheduleSerializer(many=True, read_only=True)
    is_open = serializers.SerializerMethodField()
    today_schedule = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()  
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    logo = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ['id','name','category_name','description','is_verified','logo',
                  'banner','address','country_name','city_name','neighborhood_name',
                  'average_rating','schedules', 'is_open', 'today_schedule',
                  'followers_count','location','latitude','longitude']

    def get_is_open(self, obj):
        return obj.is_open_now()
    
    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y  # latitud en GeoDjango
        return None

    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x  # longitud en GeoDjango
        return None
    
    def get_today_schedule(self, obj):
        import datetime

        weekday = datetime.datetime.now().weekday()  # 0 = Monday, 6 = Sunday
        day_number = weekday + 1  # Ajustar a tu enum: 1 = Monday, ..., 7 = Sunday

        schedule = obj.schedules.filter(day=day_number).first()
        if schedule:
            return {
                "open_time": schedule.open_time.strftime('%H:%M'),
                "close_time": schedule.close_time.strftime('%H:%M'),
            }
        return None

    def get_followers_count(self, obj):
        return obj.followers.count()
    
    def get_logo(self, obj):
        if obj.logo and hasattr(obj.logo, 'url'):
            return obj.logo.url
        return None  # o una URL de imagen por defecto

    def get_banner(self, obj):
        if obj.banner and hasattr(obj.banner, 'url'):
            return obj.banner.url
        return None  # o una URL de imagen por defecto
    

class StoreScheduleUpdateSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    
    class Meta:
        model = StoreSchedule
        fields = ['id', 'day', 'open_time', 'close_time']
        extra_kwargs = {
            'day': {'required': True},
            'open_time': {'required': False},
            'close_time': {'required': False},
        }

class StoreUpdateSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField(write_only=True, required=False)
    longitude = serializers.FloatField(write_only=True, required=False)
    schedules = StoreScheduleUpdateSerializer(many=True, required=False)
    
    class Meta:
        model = Store
        fields = [
            'name', 'description', 'nit', 'legal_name', 'foundation_date', 'address',
            'is_active', 'category', 'country', 'city', 'neighborhood', 
            'latitude', 'longitude', 'schedules'
        ]

    def validate(self, data):
        # Validación personalizada para horarios
        schedules_data = data.get('schedules', [])
        days = [s['day'] for s in schedules_data if 'day' in s]
        if len(days) != len(set(days)):
            raise serializers.ValidationError({"schedules": "No puede haber días duplicados."})
        return data

    def update(self, instance, validated_data):
        schedules_data = validated_data.pop('schedules', None)
        
        # Actualizar ubicación si viene
        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)
        if lat is not None and lng is not None:
            instance.location = Point(float(lng), float(lat))
        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Manejo de horarios si vienen en la solicitud
        if schedules_data is not None:
            self.update_schedules(instance, schedules_data)
        
        return instance

    def update_schedules(self, store, schedules_data):
        existing_schedules = {s.id: s for s in store.schedules.all()}
        updated_schedules = []
        
        for schedule_data in schedules_data:
            schedule_id = schedule_data.get('id', None)
            
            if schedule_id and schedule_id in existing_schedules:
                # Actualizar horario existente
                schedule = existing_schedules[schedule_id]
                for attr, value in schedule_data.items():
                    setattr(schedule, attr, value)
                schedule.save()
                updated_schedules.append(schedule.id)
            else:
                # Crear nuevo horario
                new_schedule = StoreSchedule.objects.create(store=store, **schedule_data)
                updated_schedules.append(new_schedule.id)
        
        # Eliminar horarios que no están en la solicitud
        for schedule_id, schedule in existing_schedules.items():
            if schedule_id not in updated_schedules:
                schedule.delete()
    
class StoreAdminSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    neighborhood_name = serializers.CharField(source='neighborhood.name', read_only=True)

    administrators = serializers.StringRelatedField(many=True) 
    schedules = StoreScheduleSerializer(many=True, read_only=True)

    is_open = serializers.SerializerMethodField()
    today_schedule = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    logo = serializers.SerializerMethodField()
    banner = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            # Campos base
            'id', 'name', 'slug', 'description', 'nit', 'legal_name',
            'is_verified', 'foundation_date', 'created_at', 'updated_at',
            'logo', 'banner', 'qr_code',

            # Relaciones geográficas y categoría
            'address', 'country', 'city', 'neighborhood', 'category',
            'country_name', 'city_name', 'neighborhood_name', 'category_name',

            # Administración y estado
            'administrators', 'is_active',

            # Datos analíticos
            'average_rating', 'total_visits', 'followers_count',

            # Ubicación geoespacial
            'location', 'latitude', 'longitude',

            # Horarios
            'schedules', 'is_open', 'today_schedule'
        ]
        
    def get_is_open(self, obj):
        return obj.is_open_now()

    def get_today_schedule(self, obj):
        import datetime
        # weekday() da 0 para lunes ... 6 para domingo, sumamos 1 para que coincida
        today_num = datetime.datetime.now().weekday() + 1
        schedule = obj.schedules.filter(day=today_num).first()
        if schedule:
            return {
                "open_time": schedule.open_time.strftime('%H:%M'),
                "close_time": schedule.close_time.strftime('%H:%M'),
            }
        return None


    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_latitude(self, obj):
        if obj.location:
            return obj.location.y
        return None

    def get_longitude(self, obj):
        if obj.location:
            return obj.location.x
        return None
    
    def get_logo(self, obj):
        if obj.logo and hasattr(obj.logo, 'url'):
            return obj.logo.url
        return None  # o una URL de imagen por defecto

    def get_banner(self, obj):
        if obj.banner and hasattr(obj.banner, 'url'):
            return obj.banner.url
        return None  # o una URL de imagen por defecto

class ShippingZoneSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source='country.name', read_only=True)
    city_name = serializers.CharField(source='city.name', read_only=True)
    neighborhood_name = serializers.CharField(source='neighborhood.name', read_only=True)

    class Meta:
        model = ShippingZone
        fields = [
            'id', 'store', 'country', 'city', 'neighborhood',
            'country_name', 'city_name', 'neighborhood_name'
        ]

    def validate(self, data):
        store = data.get('store')
        country = data.get('country')
        city = data.get('city')
        neighborhood = data.get('neighborhood')

        filters = {
            'store': store,
            'country': country,
            'city': city,
            'neighborhood__isnull': neighborhood is None
        }

        if neighborhood:
            filters['neighborhood'] = neighborhood

        qs = ShippingZone.objects.filter(**filters)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Ya existe una zona de envío con esta ubicación para esta tienda.")
        
        return data

class ShippingMethodSerializer(serializers.ModelSerializer):
    name_display = serializers.CharField(source='get_name_display', read_only=True)

    base_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False
    )
    estimated_days = serializers.IntegerField(required=False)

    class Meta:
        model = ShippingMethod
        fields = [
            'id', 'store', 'name', 'description', 'name_display',
            'base_cost', 'estimated_days', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class ShippingMethodZoneSerializer(serializers.ModelSerializer):
    shipping_method_name = serializers.CharField(source='shipping_method.get_name_display', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = ShippingMethodZone
        fields = [
            'id',
            'shipping_method', 'zone',
            'custom_cost', 'custom_days',
            'shipping_method_name', 'zone_name'
        ]

    def validate(self, data):
        method = data.get('shipping_method')
        zone = data.get('zone')
        if ShippingMethodZone.objects.filter(shipping_method=method, zone=zone).exists():
            raise serializers.ValidationError("Ya existe esta relación método-zona.")
        return data

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'store', 'name', 'account_name', 'account_number', 'payment_link', 'qr_code', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_active'] 


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = '__all__'

class StoreStatsSerializer(serializers.ModelSerializer):
    followers_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'average_rating', 'total_visits', 'followers_count']
    
    def get_followers_count(self, obj):
        return obj.followers.count()

#Lista de categorias principales, es decir de tiendas.
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id','name','icon_name']
 
class CategoryProductSerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = CategoryProduct
        fields = ['id', 'name', 'store', 'parent', 'slug', 'subcategories']

    def get_subcategories(self, obj):
        subcats = CategoryProduct.objects.filter(parent=obj)
        return CategoryProductSerializer(subcats, many=True).data
 
#Crear un reviaw hacia una tienda
class CreateReviewSerializer(serializers.ModelSerializer):
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[MaxLengthValidator(300)]
    )
    class Meta:
        model = Review
        fields = ['rating', 'comment'] 
        
class UserPublicSerializer(serializers.ModelSerializer):
    initials = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['username','initials']
        
    def get_initials(self, obj):
        return obj.initials  # usa la propiedad del modelo

class ReviewSerializer(serializers.ModelSerializer):
    user = UserPublicSerializer(read_only=True)   
    
    class Meta:
        model = Review
        fields = ['rating', 'comment','user','created_at'] 

class PaymentMethodNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'name']

class ComboItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComboItem
        fields = ['product_id', 'sku', 'quantity'] 

    def validate(self, data):
        instance = ComboItem(**data)
        instance.clean()
        return data


class ComboCreateSerializer(serializers.ModelSerializer):
    items = ComboItemCreateSerializer(many=True)

    class Meta:
        model = Combo
        fields = ['id', 'name', 'description', 'image', 'price', 'items']

    def create(self, validated_data):
        request = self.context['request']
        user = request.user

        # Obtener la tienda asociada al usuario
        store = user.stores.first()  # O lógica para seleccionar tienda específica si hay varias

        items_data = validated_data.pop('items')
        combo = Combo.objects.create(store=store, **validated_data)

        for item_data in items_data:
            ComboItem.objects.create(combo=combo, **item_data)

        return combo


class ComboSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Combo
        fields = [
            'id',
            'name',
            'description',
            'image',
            'price',
            'created_at',
        ]

    def get_image(self, obj):
        if obj.image:
            return obj.image.url  # esto da la ruta relativa: /media/...
        return None

class ComboItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    available_variants = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()  

    class Meta:
        model = ComboItem
        fields = [
            'id',
            'product_id',
            'sku',
            'quantity',
            'selected_options',
            'product_name',
            'product_image',
            'available_variants',
            'stock', 
        ]

    def get_product_name(self, obj):
        product = get_product_by_id(str(obj.product_id))
        return product.get("name") if product else None

    def get_product_image(self, obj):
        product = get_product_by_id(str(obj.product_id))
        media = product.get("media", [])
        return media[0].get("url") if media else None

    def get_available_variants(self, obj):
        product = get_product_by_id(str(obj.product_id))
        if not product:
            return []

        variants = product.get("variants", [])
        return [
            {
                "sku": v.get("sku"),
                "options": v.get("options", {}),
                "stock": v.get("stock", 0)  # Aquí se añade el stock directo
            }
            for v in variants
        ]

    def get_stock(self, obj):
            product = get_product_by_id(str(obj.product_id))
            if not product:
                return 0

            # Solo mostramos stock general si NO hay variantes
            variants = product.get("variants", [])
            if not variants:
                return product.get("stock", 0)
            return None 


class ComboDetailSerializer(serializers.ModelSerializer):
    items = ComboItemSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Combo
        fields = ['id','store', 'name', 'description', 'image', 'price', 'items']

    def get_image(self, obj):
        if obj.image:
            return obj.image.url  # esto da la ruta relativa: /media/...
        return None

    
