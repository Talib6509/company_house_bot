FROM python:3.12-slim

# Prevent python from writing pyc files & enable stdout logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy full project
COPY . .

# Streamlit config
RUN mkdir -p /root/.streamlit && \
    echo "\
[server]\n\
headless = true\n\
enableCORS = false\n\
port = 8501\n\
" > /root/.streamlit/config.toml

EXPOSE 8501

CMD ["streamlit", "run", "streamapp.py", "--server.port=8501", "--server.address=0.0.0.0"]