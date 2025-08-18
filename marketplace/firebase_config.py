# marketplace/firebase_config.py
import os
from firebase_admin import credentials, initialize_app
from django.conf import settings

cred_path = os.path.join(settings.BASE_DIR, 'marketplace', 'firebasedocument.json')
cred = credentials.Certificate(cred_path)
firebase_app = initialize_app(cred)  # Renombrado como firebase_app por claridad
