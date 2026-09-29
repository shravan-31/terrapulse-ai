FROM python:3.11-slim

# Install GDAL system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL env for rasterio
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Non-root user
RUN useradd -m -u 1000 satquery
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R satquery:satquery /app

USER satquery

# Default API server command (migrations are a controlled deployment step)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
