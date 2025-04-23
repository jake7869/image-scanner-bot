FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy all files from your repo into the container
COPY . .

# Install required libraries
RUN pip install --no-cache-dir -r requirements.txt

# Start the bot
CMD ["python", "image_bot.py"]
