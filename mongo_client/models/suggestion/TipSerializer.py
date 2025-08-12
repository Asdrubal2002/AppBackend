from rest_framework import serializers
from bson import ObjectId
from datetime import datetime

from apps.stores.models import Category

class TipSerializer(serializers.Serializer):
    _id = serializers.CharField(read_only=True)
    contenido = serializers.CharField(max_length=500)
    categoria_slug = serializers.SlugField(write_only=True)
    categoria_name = serializers.CharField(read_only=True)
    categoria_type = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def validate_categoria_slug(self, value):
        try:
            categoria = Category.objects.get(slug=value)
            self.context["categoria_obj"] = categoria
            return value
        except Category.DoesNotExist:
            raise serializers.ValidationError("Categoría no válida.")

    def create(self, validated_data):
        categoria = self.context["categoria_obj"]
        now = datetime.utcnow()
        doc = {
            "contenido": validated_data["contenido"],
            "categoria_slug": categoria.slug,
            "categoria_name": categoria.name,
            "categoria_type": categoria.type,
            "created_at": now,
            "updated_at": now,
        }
        result = self.context["collection"].insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return doc

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['_id'] = str(instance.get('_id'))
        return rep
    
    
#  ¿Por qué incluirlos?

#     Control de versiones
#     Te permite saber si el tip fue actualizado (y cuándo), ideal si en un futuro quieres mostrar “Tips actualizados recientemente”.

#     Orden cronológico
#     Puedes ordenarlos por fecha en reportes o dashboards de administración.

#     Depuración y auditoría
#     Sirve para rastrear cuándo fue creado un tip, útil en debugging o control de calidad.

#     Filtros inteligentes
#     Puedes mostrar tips del mes, del día, o recientes sin complicarte.
