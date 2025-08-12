from datetime import datetime
from bson import ObjectId
from ...connection import mongo_db
from apps.users.models import User
from datetime import datetime
from ...connection import mongo_db

from django.contrib.auth import get_user_model

User = get_user_model()

comments_collection = mongo_db["comments"]
posts_collection = mongo_db["post"]

def increment_post_comments_count(post_id):
    try:
        oid = ObjectId(post_id)
    except Exception:
        oid = post_id

    result = posts_collection.update_one(
        {"_id": oid},
        {"$inc": {"comments_count": 1}}
    )
    print(f"Incrementar comentarios para post_id={post_id}: matched={result.matched_count}, modified={result.modified_count}")

def create_comment(data):
    now = datetime.utcnow()

    try:
        user = User.objects.get(id=data["user_id"])
        username = user.username
    except User.DoesNotExist:
        username = f"User{data['user_id']}"
        user = None  # en caso de necesitarlo luego

    comment = {
        "post_id": ObjectId(data["post_id"]),
        "user_id": data["user_id"],
        "content": data["content"],
        "created_at": now,
        "updated_at": now,
        "user_name": username,
    }

    inserted = comments_collection.insert_one(comment)
    increment_post_comments_count(str(data["post_id"]))

    comment["_id"] = inserted.inserted_id  # Añadir el ID al comentario original
    return comment, user


def get_post_comments(post_id, page=1, page_size=10):
    skip = (page - 1) * page_size

    total = comments_collection.count_documents({"post_id": ObjectId(post_id)})

    comments_cursor = comments_collection.find(
        {"post_id": ObjectId(post_id)}
    ).sort("created_at", -1).skip(skip).limit(page_size)

    comments = list(comments_cursor)

    for comment in comments:
        comment["_id"] = str(comment["_id"])
        comment["post_id"] = str(comment["post_id"])
        comment["user_id"] = str(comment["user_id"])

    return comments, total

