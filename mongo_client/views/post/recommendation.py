from ...connection import mongo_db
posts_collection = mongo_db["post"]
from collections import Counter
from django.core.paginator import Paginator
from collections import defaultdict
import random

# sistema de recomendaciones basado en reglas
# recomendaciones usando reglas inteligentes (tienda, categoría, ubicación).

def get_liked_posts_by_user(user):
    return list(
        posts_collection.find({
            "liked_by": {"$in": [user.id]}
        })
    )

def build_user_profile(user):
    liked_posts = get_liked_posts_by_user(user)
    if not liked_posts:
        return None

    store_ids = Counter()
    categories = Counter()
    countries = Counter()
    cities = Counter()
    neighborhoods = Counter()

    for post in liked_posts:
        store = post.get("store", {})
        store_ids[store.get("_id")] += 1
        categories[store.get("category")] += 1
        countries[store.get("country")] += 1
        cities[store.get("city")] += 1
        neighborhoods[store.get("neighborhood")] += 1

    return {
        "top_store_ids": [s for s, _ in store_ids.most_common(3)],
        "top_categories": [c for c, _ in categories.most_common(3)],
        "top_countries": [c for c, _ in countries.most_common(3)],
        "top_cities": [c for c, _ in cities.most_common(3)],
        "top_neighborhoods": [n for n, _ in neighborhoods.most_common(3)],
    }


def recommend_similar_posts(user, page=1, limit=100):
    profile = build_user_profile(user)
    if not profile:
        return {"posts": [], "page": 1, "total_pages": 0, "total_posts": 0}

    query = {
        "liked_by": {"$ne": user.id},
        "$or": [
            {"store_id": {"$in": profile["top_store_ids"]}},
            {"store.category": {"$in": profile["top_categories"]}},
            {"store.country": {"$in": profile["top_countries"]}},
            {"store.city": {"$in": profile["top_cities"]}},
            {"store.neighborhood": {"$in": profile["top_neighborhoods"]}},
        ]
    }

    # Cargar más posts para poder aplicar aleatoriedad
    all_posts = list(posts_collection.find(query).limit(100))  # Límite amplio
    random.shuffle(all_posts)  # Desordenar el orden

    # ✅ Eliminar duplicados por _id
    seen = set()
    unique_posts = []
    for post in all_posts:
        pid = str(post.get('_id'))
        if pid not in seen:
            seen.add(pid)
            unique_posts.append(post)

    # (Opcional) Limitar a máximo N posts por tienda
    max_per_store = 3
    grouped = defaultdict(list)
    balanced_posts = []

    for post in unique_posts:
        store_id = post.get("store_id")
        if len(grouped[store_id]) < max_per_store:
            grouped[store_id].append(post)
            balanced_posts.append(post)

    # Paginación después de mezclar y balancear
    paginator = Paginator(balanced_posts, limit)
    if page > paginator.num_pages and paginator.num_pages > 0:
        page = paginator.num_pages

    page_posts = paginator.page(page).object_list

    # Asegurar consistencia
    for p in page_posts:
        p.setdefault("liked_by", [])

    return {
        "posts": page_posts,
        "page": page,
        "total_pages": paginator.num_pages,
        "total_posts": paginator.count,
    }
