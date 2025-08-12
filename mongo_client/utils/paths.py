def product_media_upload_path(store_slug, product_slug, filename):
    return f'stores/{store_slug}/products/{product_slug}/{filename}'

def post_media_upload_path(store_slug, post_id, filename):
    return f'stores/{store_slug}/posts/{post_id}/{filename}'
