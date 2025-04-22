
FROM python:3.10-slim

# Install Tesseract OCR
RUN apt-get update && apt-get install -y tesseract-ocr libglib2.0-0 libsm6 libxext6 libxrender-dev

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install -r requirements.txt

# Start the bot
CMD ["python", "image_scanner_bot.py"]
