FROM python:3.11-slim

# Create a working directory.
WORKDIR /usr/src/app

# Install Python dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the codebase into the image
COPY . ./

ENV REDIS_URL redis://redis:6379

RUN chmod +x ./start.sh

# Finally, run gunicorn.
CMD ["./start.sh"]
