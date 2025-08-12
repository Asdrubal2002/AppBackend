from rest_framework import serializers

class CommentSerializer(serializers.Serializer):
    _id = serializers.CharField(read_only=True)
    post_id = serializers.CharField(required=True)
    user_id = serializers.CharField(required=True)
    content = serializers.CharField(max_length=500, required=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    username = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()  # solo para mostrar
    
    def get_username(self, obj):
        return obj.get("user_name", f"User{obj.get('user_id')}")
    
    def get_initials(self, obj):
        name = obj.get("user_name", "") or ""
        parts = name.strip().split()
        initials = ""

        if len(parts) >= 2:
            initials = parts[0][0] + parts[1][0]
        elif len(parts) == 1:
            initials = parts[0][:2]
        else:
            username = obj.get("username", "")
            initials = username[:2]

        return initials.upper()



    
    
