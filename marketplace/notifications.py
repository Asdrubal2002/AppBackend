# marketplace/notifications.py
from firebase_admin import messaging
from . import firebase_config  # Esto asegura que firebase_admin esté inicializado

def send_push_notification(token, title, body):
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        token=token,
    )

    try:
        response = messaging.send(message)
        print(f'✅ Notificación enviada: {response}')
        return response
    except Exception as e:
        print(f'❌ Error al enviar notificación: {e}')
        return None
