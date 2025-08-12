import random

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.stores.models import Category
from ...models.suggestion.TipSerializer import TipSerializer
from ...connection import mongo_db
tips_collection = mongo_db["tips"]

class TipCreateView(APIView):
    def post(self, request):
        serializer = TipSerializer(data=request.data, context={"collection": tips_collection})
        if serializer.is_valid():
            tip = serializer.save()
            return Response(tip, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RandomTipByCategoryView(APIView):
    def get(self, request, slug):
        try:
            categoria = Category.objects.get(slug=slug)
        except Category.DoesNotExist:
            return Response({"error": "Categoría no válida"}, status=status.HTTP_400_BAD_REQUEST)

        tips = list(tips_collection.find({"categoria_slug": slug}))
        if not tips:
            return Response({"message": "No hay tips para esta categoría"}, status=status.HTTP_404_NOT_FOUND)

        tip = random.choice(tips)
        tip["_id"] = str(tip["_id"])
        return Response(tip)
