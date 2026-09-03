FROM python:3.12-slim

WORKDIR /app

# Install Icarus Verilog
RUN apt-get update \
    && apt-get install -y --no-install-recommends iverilog \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Render uses port 10000
EXPOSE 10000

CMD ["gunicorn", "ai_rtl.wsgi:application", "--workers", "1", "--timeout", "180", "--bind", "0.0.0.0:10000"]