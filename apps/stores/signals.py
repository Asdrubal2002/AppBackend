# en signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from mongo_client.models.post.post import update_post
from apps.stores.models import Store

@receiver(post_save, sender=Store)
def update_embedded_store_data(sender, instance, **kwargs):
    update_post(instance)
    

