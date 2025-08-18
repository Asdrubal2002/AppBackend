import os
import json
from firebase_admin import credentials, initialize_app

firebase_config = os.getenv("FIREBASE_CONFIG")

if firebase_config:
    cred_dict = json.loads(firebase_config)
    cred = credentials.Certificate(cred_dict)
else:
    from django.conf import settings
    cred_path = os.path.join(settings.BASE_DIR, 'marketplace', 'firebasedocument.json')
    cred = credentials.Certificate(cred_path)

firebase_app = initialize_app(cred)
