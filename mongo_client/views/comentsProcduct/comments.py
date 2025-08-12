from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import api_view, permission_classes
from ...models.comentsProduct.comments import create_comment, get_post_comments
from ...models.comentsProduct.serializers.serializersComments import CommentSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comment_create_view(request):
    data = request.data
    data['user_id'] = request.user.id

    if not data.get("post_id") or not data.get("content"):
        return Response({"error": "post_id y content son requeridos."}, status=400)

    comment, user = create_comment(data)

    return Response({
        "message": "Comentario creado",
        "comment": {
            "_id": str(comment["_id"]),
            "content": comment["content"],
            "created_at": comment["created_at"],
            "username": comment["user_name"],
            "initials": user.initials if hasattr(user, "initials") else comment["user_name"][:2].upper()
        }
    })
    
    
    
    
@api_view(['GET'])
@permission_classes([AllowAny])
def comments_list_view(request, post_id):
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))

    comments, total = get_post_comments(post_id, page, page_size)
    serializer = CommentSerializer(comments, many=True)

    return Response({
        "results": serializer.data,
        "count": total,
        "page_size": page_size,
        "next": page * page_size < total,
        "previous": page > 1,
    })

