FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# main.py no longer calls Base.metadata.create_all() — schema is Alembic's
# job now. Run migrations first, then start the server. If migrations fail,
# the container fails to start rather than booting against a broken schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]