from django.db import models
from apps.stores.models import Store
from apps.users.models import User

# Create your models here.

# class Notification(models.Model):
#     NOTIFICATION_TYPES = [
#         ('post', 'Publicación'),
#         ('comment', 'Comentario'),
#         ('follow', 'Nuevo seguidor'),
#     ]

#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
#     type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
#     title = models.CharField(max_length=255)
#     body = models.TextField(blank=True)
#     read = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)

#     post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE)
#     store = models.ForeignKey(Store, null=True, blank=True, on_delete=models.CASCADE)

#     def __str__(self):
#         return f'{self.type} -> {self.user.username}'