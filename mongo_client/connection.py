from pymongo import MongoClient
from django.conf import settings

client = MongoClient(settings.MONGO_URI)
mongo_db = client[settings.MONGO_DB_NAME]
