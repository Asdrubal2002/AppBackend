FROM python:3.9

# Instalar dependencias del sistema necesarias para GeoDjango y PostGIS
RUN apt-get update && apt-get install -y \
    binutils \
    gdal-bin \
    libproj-dev \
    libgdal-dev \
    libgeos-dev \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Establece el symlink de libgdal.so si no existe
RUN bash -c 'ln -s $(find /usr/lib /usr/lib64 -name "libgdal.so.*" | head -n 1) /usr/lib/libgdal.so || true'

# Configura la variable de entorno
ENV GDAL_LIBRARY_PATH=/usr/lib/libgdal.so

# Directorio de trabajo
WORKDIR /app

# Copiar requirements y dependencias
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install -r requirements.txt && \
    python -m spacy download es_core_news_sm 

# Copiar código
COPY . .


EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
