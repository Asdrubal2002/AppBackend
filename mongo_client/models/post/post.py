from datetime import datetime
from bson import ObjectId
from ...connection import mongo_db


posts_collection = mongo_db["post"]

def create_post(post_data):
    post = post_data.copy()

    now = datetime.utcnow()
    post["created_at"] = now
    post["updated_at"] = now

    result = posts_collection.insert_one(post)
    post["_id"] = str(result.inserted_id)

    return post

def process_post_with_absolute_media(post, request):
    """
    Mantiene las rutas relativas en media y logo de tienda.
    """
    if not post:
        return None

    post["_id"] = str(post["_id"])

    # Dejar las rutas relativas en media
    processed_media = []
    for item in post.get("media", []):
        processed_media.append({
            "url": item.get("url", ""),  # sin build_absolute_uri
            "type": item.get("type", "image"),
            "name": item.get("name"),
            "size": item.get("size"),
            "content_type": item.get("content_type"),
            "media_type": item.get("media_type"),
        })
    post["media"] = processed_media

    # Dejar la ruta relativa del logo de la tienda
    store_logo = post.get("store_logo")
    if store_logo and store_logo.startswith("/"):
        post["store_logo"] = store_logo  # no se convierte

    return post


def get_post_by_id(post_id):
    try:
        return posts_collection.find_one({"_id": ObjectId(post_id)})
    except:
        return None

def update_post(post_id, data):
    if isinstance(post_id, str):
        post_id = ObjectId(post_id)

    posts_collection.update_one(
        {"_id": post_id},
        {"$set": data}
    )

    return posts_collection.find_one({"_id": post_id})
