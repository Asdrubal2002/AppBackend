from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from apps.locations.models import Country, City, Neighborhood 
from django.core.exceptions import ValidationError


def user_profile_photo_path(instance, filename):
    # Ruta personalizada para almacenar la foto del usuario
    return f"user_photos/{instance.username}/{filename}"

# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('The username is required')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra_fields)
    
class User(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=100)
    last_name=models.CharField(max_length=100, null=True, blank=True)
    cellphone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')], null=True, blank=True)
    document_number = models.CharField(max_length=30, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_seller = models.BooleanField(default=False)
    is_buyer = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    verified_cellphone = models.BooleanField(default=False)
    verified_mail = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    registration_date = models.DateTimeField(auto_now_add=True)

    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.SET_NULL, null=True, blank=True)

    followed_stores = models.ManyToManyField('stores.Store', related_name='followers', blank=True)    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    def clean(self):
        super().clean()
        if self.is_seller and not self.document_number:
            raise ValidationError("Los vendedores deben tener un número de documento registrado.")

    def save(self, *args, **kwargs):
        if self.pk:
            old = User.objects.get(pk=self.pk)
            if old.document_number and self.document_number != old.document_number:
                raise ValueError("El número de documento no puede modificarse una vez asignado.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.name})"
    
    

    @property
    def initials(self):
        initials = ''
        if self.name:
            initials += self.name.strip()[0].upper()
        if self.last_name:
            initials += self.last_name.strip()[0].upper()
        return initials or self.username[:2].upper()


class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    fcm_token = models.CharField(max_length=255, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dispositivo de {self.user.username}"