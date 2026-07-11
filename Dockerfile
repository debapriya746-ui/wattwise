# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory to /app
WORKDIR /app

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into /app
COPY . .

# Expose port 8080
EXPOSE 8080

# Run Streamlit on container start
CMD ["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0"]
