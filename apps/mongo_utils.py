# mongo_utils.py
import pymongo
from django.conf import settings
from bson import ObjectId  # Importa ObjectId
from pymongo.errors import PyMongoError
from bson import ObjectId, errors as bson_errors

def get_mongo_client():
    return pymongo.MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000
    )

def get_mongo_db():
    return get_mongo_client()[settings.MONGO_DB_NAME]

def get_product_by_id(product_id):
    try:
        # Si el ID no es un ObjectId válido (como "combo-1"), retorna None
        if not ObjectId.is_valid(product_id):
            return None

        db = get_mongo_db()
        return db.products.find_one({"_id": ObjectId(product_id)})
    except (PyMongoError, bson_errors.InvalidId, TypeError) as e:
        print(f"MongoDB Error: {str(e)}")
        return None