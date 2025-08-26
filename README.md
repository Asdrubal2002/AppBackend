# Ruvlo

## 📌 Descripción
Este backend está desarrollado en **Python -Django REST Framework** y gestiona toda la lógica de negocio relacionada con negocios, productos, ofertas, cupones, 
ventas y perfiles de usuario.  
Permite registrar los negocios,usuarios, calcular márgenes de ganancia y consultar reportes de forma sencilla.

## 📂 Estructura básica
El sistema completo está dividido en tres repositorios/proyectos independientes:

- **Backend** → API desarrollada en Django REST Framework, gestiona productos, ventas y reportes.  
- **[Frontend (App)](https://github.com/Asdrubal2002/App)** → Interfaz principal de la aplicación, desarrollada en React/Vite.  
- **[Landing Page](https://github.com/Asdrubal2002/Presentation-Ruvlo-App)** → Sitio público de presentación e información del proyecto.


## 🛠️ Tecnologías utilizadas
- Python 3.11
- Django 4.2.21
- Django REST Framework
- PostgreSQL / PostGis
- Mongo DB
- firebase
- cloudinary
- JWT
- Ionicons
- Leaflet Map

### 📁 Estructura interna del Backend

- **apps/** → Contiene las aplicaciones internas de Django (negocios, cuentas, etc.)  
- **marketplace/** → Módulo principal que gestiona la lógica del marketplace  
- **mongo_client/** → Configuración y cliente para la conexión con MongoDB  
- **manage.py** → Script de administración principal de Django  
- **requirements.txt** → Lista de dependencias del proyecto  
- **Dockerfile** → Configuración para crear la imagen Docker del backend  
- **.gitignore** → Archivos y carpetas que no se versionan en Git  
- **README.md** → Documentación del backend  

### 📦 Estructura de Apps

- **carts/** → Gestión de carritos/canasta de compras.  
- **locations/** → Manejo de ubicaciones y localidades nacionales e internacionales.  
- **notification/** → Sistema de notificaciones internas (avisos a usuarios/tiendas).  
- **stores/** → Administración de las negocios registradas en la aplicación.  
- **users/** → Gestión de usuarios, roles y autenticación.
- **post/** → Gestión de publicaciones de cada negocio.  
- **CommentsProduct/** → Administración de los comentarios de cada producto.  
- **product/** → Sistema de administración de productos.  


### DOCUMENTACIÓN SOBRE EL PROYECTO

- **[Documentación](https://github.com/Asdrubal2002/AppBackend/blob/main/Documentation.pdf)** → Objetivos, cronograma.


### DOCUMENTACIÓN SOBRE EL PROYECTO
- **[App desplegada](https://appgallery.cloud.huawei.com/ag/n/app/C115034911?locale=es_US&source=appshare&subsource=C115034911&shareTo=com.android.bluetooth&shareFrom=appmarket&shareIds=7c0fe389d25b4bc193975d0a0009e387_com.android.bluetooth&callType=SHARE)**