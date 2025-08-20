# Ruvlo

## 📌 Descripción
Este backend está desarrollado en **Python -Django REST Framework** y gestiona toda la lógica de negocio relacionada con negocios, productos, ofertas, cupones, 
ventas y perfiles de usuario.  
Permite registrar los negocios,usuarios, calcular márgenes de ganancia y consultar reportes de forma sencilla.

## 🛠️ Tecnologías utilizadas
- Python 3.11
- Django 4.2.21
- Django REST Framework
- PostgreSQL / PostGis
- Mongo DB
- firebase
- cloudinary
- JWT

## 📂 Estructura básica
El sistema completo está dividido en tres repositorios/proyectos independientes:

- **Backend** → API desarrollada en Django REST Framework, gestiona productos, ventas y reportes.  
- **[Frontend (App)](https://github.com/Asdrubal2002/App)** → Interfaz principal de la plataforma, desarrollada en React/Vite.  
- **[Landing Page](https://github.com/Asdrubal2002/Presentation-Ruvlo-App)** → Sitio público de presentación e información del proyecto.

### 📁 Estructura interna del Backend
backend/
│── apps/             # Contiene las aplicaciones internas de Django (productos, negocios, etc.)
│── marketplace/      # Módulo principal que gestiona la lógica del marketplace
│── mongo_client/     # Configuración y cliente para la conexión con MongoDB
│── manage.py         # Script de administración principal de Django
│── requirements.txt  # Lista de dependencias del proyecto
│── Dockerfile        # Configuración para crear la imagen Docker del backend
│── .gitignore        # Archivos y carpetas que no se versionan en Git
│── README.md         # Documentación del backend
