# Use the official Python image as the base
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    aria2 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the application code
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose any necessary ports (if applicable)
# EXPOSE 8000

# Define environment variables (if needed)
# ENV VARIABLE_NAME=value

# Define the default command to run the application
CMD ["python", "bot.py"]
