from ...connection import mongo_db
from bson.objectid import ObjectId
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import secrets
import string
from django.core.files.uploadedfile import InMemoryUploadedFile
from datetime import datetime, date
from math import sqrt
from math import sqrt, isfinite
from datetime import date
import sys


def force_log(*args):
    sys.stderr.write(" ".join(str(a) for a in args) + "\n")
    sys.stderr.flush()


products_collection = mongo_db["products"]

def generate_random_slug(length=20):
    chars = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

# asegurar que los objetos date se conviertan a datetime antes de guardar en MongoDB, 
# que no maneja bien date puros.
def convert_dates(data):
    """
    Convierte datetime.date a datetime.datetime para compatibilidad con MongoDB.
    """
    for key, value in data.items():
        if isinstance(value, date) and not isinstance(value, datetime):
            data[key] = datetime.combine(value, datetime.min.time())
        elif isinstance(value, dict):
            data[key] = convert_dates(value)
        elif isinstance(value, list):
            data[key] = [convert_dates(item) if isinstance(item, dict) else item for item in value]
    return data

def create_product(product_data):
    product = product_data.copy()
    product = convert_dates(product)  # Convertimos fechas antes del insert

    # Generar slug automático si no viene
    if not product.get("slug"):
        slug = generate_random_slug()
        # Asegurar que sea único
        while products_collection.find_one({"slug": slug}):
            slug = generate_random_slug()
        product["slug"] = slug

    result = products_collection.insert_one(product)
    product["_id"] = str(result.inserted_id)
    return product

def get_product(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})
    if product:
        product["_id"] = str(product["_id"])
    return product

def update_product(product_id, update_data):
    """
    Actualizar un producto por su id
    update_data: dict con los campos a actualizar
    """
    update_data = convert_dates(update_data)

    result = products_collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": update_data}
    )
    return result.modified_count

def delete_product(product_id):
    """
    Eliminar un producto por su id
    """
    result = products_collection.delete_one({"_id": ObjectId(product_id)})
    return result.deleted_count

"""
Pasos (shell Mongo)

🧩 Paso 1: Crear índice de texto en la colección products
// 0 · Entrar a la base correcta
use marketplace          // ← pon el nombre real de tu base

// 1 · Índice geoespacial
db.products.createIndex({ "store.location": "2dsphere" })

// 2 · Índice de texto
db.products.createIndex({
  name:        "text",
  description: "text",
  brand:       "text",
  keywords:    "text"
}, { default_language: "spanish" })   // opcional

// 3 · Verificar
db.products.getIndexes()


"""

def list_products(
    store_id=None, country_id=None, city_id=None, neighborhood_id=None,
    page=1, page_size=10, filters=None, lat=None, lon=None
):
    base = {"is_active": True}
    if store_id:        base["store_id"]        = store_id
    if country_id:      base["country_id"]      = int(country_id)
    if city_id:         base["city_id"]         = int(city_id)
    if neighborhood_id: base["neighborhood_id"] = int(neighborhood_id)

    # -------- filtros ---------------------------------------
    search = None
    if filters:
        search = filters.get("search") or None

        if filters.get("name"):
            base["name"] = {"$regex": filters["name"], "$options": "i"}

        if filters.get("description"):
            base["description"] = {"$regex": filters["description"], "$options": "i"}

        if filters.get("brand"):
            base["brand"] = {"$regex": filters["brand"], "$options": "i"}

        if filters.get("keywords"):
            base["keywords"] = {"$regex": filters["keywords"], "$options": "i"}

        if filters.get("category") is not None:
            try:
                base["category"] = int(filters["category"])
            except ValueError:
                pass  # O ignora este filtro si falla la conversión

        if filters.get("store_category") is not None:
            try:
                base["store_category"] = int(filters["store_category"])
            except ValueError:
                pass

        # Filtro por precio mínimo y máximo
        price_filter = {}
        if filters.get("price_min") is not None:
            try:
                price_filter["$gte"] = float(filters["price_min"])
            except ValueError:
                pass

        if filters.get("price_max") is not None:
            try:
                price_filter["$lte"] = float(filters["price_max"])
            except ValueError:
                pass

        if price_filter:
            base["price"] = price_filter

    # -------- pipeline ---------------------------------------
    pipe = []

    if lat is not None and lon is not None:
        pipe.append({
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "distanceField": "_distance",
                "maxDistance": 1000,
                "spherical": True,
                "query": base
            }
        })
    else:
        pipe.append({"$match": base})

    # búsqueda rápida
    if search:
        rgx = {"$regex": search, "$options": "i"}
        pipe.append({"$match": {"$or": [
            {"name": rgx},
            {"description": rgx},
            {"brand": rgx},
            {"keywords": rgx}
        ]}})

    pipe += [
        {"$sort": {"created_at": -1}},  # -1 para descendente, 1 para ascendente
        {"$skip": (page - 1) * page_size},
        {"$limit": page_size},
        {"$project": {
            "name": 1,
            "description": 1,
            "price": 1,
            "media": 1,
            "category": 1,
            "slug": 1,
            "discount_percentage": 1,
            "discount_start": 1,
            "discount_end": 1,
            "store": 1,
            "_distance": 1,
            "discounted_price": {"$literal": None},
            "stock": 1,
            "sku":1,
        }}
    ]

    docs = list(products_collection.aggregate(pipe))
    # Pipeline para contar total con todos los filtros aplicados (incluyendo search)
    count_pipe = [p for p in pipe if "$match" in p or "$geoNear" in p]
    count_pipe.append({"$count": "total"})

    count_result = list(products_collection.aggregate(count_pipe))
    total = count_result[0]["total"] if count_result else 0


    today = date.today()
    for d in docs:
        d["_id"] = str(d["_id"])
        d["discounted_price"] = apply_discount(
            d["price"],
            d.get("discount_percentage"),
            d.get("discount_start"),
            d.get("discount_end"),
            today
        )

    return {
        "results": docs,
        "count": total,
        "page_size": page_size,
        "next": page * page_size < total,
        "previous": page > 1,
    }



def process_products_with_images(products, request):
    for prod in products:
        prod["_id"] = str(prod["_id"])

        media_items = prod.get("media", [])
        preview_image_url = None

        # Buscar la primera imagen tipo 'image'
        for media in media_items:
            if media.get("type") == "image":
                preview_image_url = media.get("url", "")
                break  # Solo la primera imagen

        prod["preview_image"] = preview_image_url
        prod["media"] = [] 

        # Eliminar campo 'images' si existe por si acaso
        prod.pop("images", None)

    return products

def process_single_product_with_media(product, request):
    """
    Devuelve solo rutas relativas en el campo media
    y elimina los campos preview_image e images si existen.
    """
    if not product:
        return None

    product["_id"] = str(product["_id"])

    media = product.get("media", [])
    processed_media = []

    for item in media:
        url = item.get("url", "")

        media_item = {
            "url": url,  # ruta tal cual, sin convertirla en absoluta
            "type": item.get("type", "image")
        }
        processed_media.append(media_item)

    product["media"] = processed_media

    product.pop("preview_image", None)
    product.pop("images", None)

    return product


def compress_image(file, max_size=1024, quality=75):
    img = Image.open(file)
    original_format = img.format  # 'PNG', 'JPEG', etc.
    img = img.convert('RGB')

    # Redimensionar si excede tamaño
    if max(img.size) > max_size:
        ratio = max_size / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    # Si es PNG pequeño, devuélvelo tal cual
    if original_format == 'PNG' and file.size < 100 * 1024:
        file.seek(0)
        return file, file.name

    # Comprimir a JPEG
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=quality)
    buffer.seek(0)
    new_name = file.name.rsplit('.', 1)[0] + '_compressed.jpg'
    compressed_file = InMemoryUploadedFile(
        buffer,
        None,
        new_name,
        'image/jpeg',
        buffer.getbuffer().nbytes,
        None
    )

    return compressed_file, new_name

def delete_products_by_store(store_id):
    """
    Elimina todos los productos de una tienda específica.
    """
    result = products_collection.delete_many({"store_id": int(store_id)})
    return result.deleted_count

def apply_discount(price, discount, start, end, today=None):
    """
    Aplica un descuento al precio si:
    - El porcentaje está definido y es mayor que 0.
    - Las fechas de inicio y fin están dentro del rango actual.
    - Las fechas pueden venir como datetime o date.
    """
    today = today or date.today()

    if not isinstance(price, (int, float)):
        return price  # o puedes lanzar una excepción si lo prefieres

    if not discount or not start or not end:
        return price

    if isinstance(start, datetime):
        start = start.date()
    if isinstance(end, datetime):
        end = end.date()

    if start <= today <= end:
        return round(price * (1 - discount / 100), 2)

    return price