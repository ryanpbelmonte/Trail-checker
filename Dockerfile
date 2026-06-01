FROM python:3.12-slim

WORKDIR /app

# Install dependencies first; Docker caches this layer if requirements don't change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app.
COPY . .

# Gunicorn listens on 8000 (see gunicorn.conf.py).
EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
