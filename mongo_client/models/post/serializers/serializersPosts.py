from rest_framework import serializers
from bson import ObjectId
from ....connection import mongo_db

from apps.stores.models import Store

posts_collection = mongo_db["post"]

class PostSerializer(serializers.Serializer):
    _id = serializers.CharField(read_only=True)
    store_id = serializers.IntegerField(required=True)

    title = serializers.CharField(max_length=150, required=True)
    content = serializers.CharField(allow_blank=True, max_length=1000, required=True)

    media_type = serializers.ChoiceField(
        choices=["image", "video", "mixed"],
        default="image",
        read_only=True
    )
    media = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    likes = serializers.IntegerField(read_only=True, default=0)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    
    is_liked = serializers.SerializerMethodField()

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    # Campos embebidos de la tienda
    store_name = serializers.SerializerMethodField()
    store_logo = serializers.SerializerMethodField()
    store_slug = serializers.SerializerMethodField()

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['_id'] = str(instance.get('_id'))
        return ret
    
    def get_store_name(self, obj):
        return obj.get("store", {}).get("name", "")

    def get_store_logo(self, obj):
        return obj.get("store", {}).get("logo", "")

    def get_store_slug(self, obj):
        return obj.get("store", {}).get("slug", "")

    def get_is_liked(self, instance):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False

        user_id = request.user.id
        liked_by = instance.get('liked_by', [])
        return user_id in liked_by

    def create(self, validated_data):
        store_id = validated_data.pop('store_id')

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            raise serializers.ValidationError("Tienda no encontrada")

        # Embebe los datos necesarios
        validated_data['store'] = {
            '_id': store.id,
            'name': store.name,
            'logo': store.logo.url if store.logo else '',
            'slug': store.slug
        }

        validated_data['store_id'] = store_id 
        
        from ..post import create_post
        return create_post(validated_data)

    def update(self, instance, validated_data):
        from ..post import update_post  # función que actualiza en DB
        from django.utils.timezone import now

        allowed_fields = ['title', 'content']

        updated_data = {}

        for field in allowed_fields:
            if field in validated_data:
                updated_data[field] = validated_data[field]

        if updated_data:
            updated_data['updated_at'] = now()
            updated_post = update_post(str(instance['_id']), updated_data)
            return updated_post

        return instance  # Si no hubo cambios, retorna el original

   