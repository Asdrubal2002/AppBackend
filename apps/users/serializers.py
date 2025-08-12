from rest_framework import serializers
from .models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Puedes agregar cualquier dato personalizado aquí
        token['username'] = user.username
        token['is_seller'] = user.is_seller
        # Lista de IDs de tiendas administradas
        token['store_ids'] = list(user.stores.values_list('id', flat=True))
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['username'] = self.user.username
        data['is_seller'] = self.user.is_seller
        data['store_ids'] = list(self.user.stores.values_list('id', flat=True))
        return data

class UserRegistrationSerializer(serializers.ModelSerializer):
    pin = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'name', 'country','pin', 'cellphone')

    def validate_pin(self, value):
        if len(value) != 4 or not value.isdigit():
            raise serializers.ValidationError("El PIN debe tener exactamente 4 dígitos numéricos.")
        return value

    def create(self, validated_data):
        pin = validated_data.pop("pin")  # Obtiene el PIN
        user = User.objects.create_user(password=pin, **validated_data)  # Crea el usuario con el PIN como contraseña
        return user

class UserSerializer(serializers.ModelSerializer):
    initials = serializers.SerializerMethodField()
   

    class Meta:
        model = User
        fields = [
            "id", "username", "name", "last_name", "cellphone",
            "email", "country", "city", "neighborhood", "date_of_birth",
            "gender", "document_number", "address", "initials"
        ]

    def get_initials(self, obj):
        return obj.initials
     
class UsernameValidationSerializer(serializers.Serializer):
    username = serializers.CharField()

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Este usuario ya existe.")
        return value
    
class UserEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'name',
            'last_name',
            'date_of_birth',
            'gender',
            'document_number',
            'address',
            'country',
            'city',
            'neighborhood',
            'email',
        ]

    def validate_document_number(self, value):
        user = self.instance
        if user and user.document_number and user.document_number != value:
            raise serializers.ValidationError("No se puede modificar el número de documento una vez asignado.")
        return value
