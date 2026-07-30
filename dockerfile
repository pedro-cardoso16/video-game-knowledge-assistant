FROM python:3.12-slim

WORKDIR /app

# Copy dependency files
COPY requirements.txt .

# Install dependencies using pip
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

RUN chmod +x startup.sh

EXPOSE 8501

# Command to execute startup script
CMD ["./startup.sh"]