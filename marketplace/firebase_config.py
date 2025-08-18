# marketplace/firebase_config.py
import os
from firebase_admin import credentials, initialize_app
from django.conf import settings

# Intenta usar el archivo secreto en Render
cred_path = "/etc/secrets/firebasedocument.json"

if not os.path.exists(cred_path):
    # Si no existe (ej: entorno local), usa el archivo normal
    cred_path = os.path.join(settings.BASE_DIR, 'marketplace', 'firebasedocument.json')

cred = credentials.Certificate(cred_path)
firebase_app = initialize_app(cred)

