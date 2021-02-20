FROM python:3.8.6-slim-buster

# Create a working directory.
WORKDIR /usr/src/app

# Install Python dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the codebase into the image
COPY . ./

ENV REDIS_URL redis://redis:6379

# Finally, run gunicorn.
CMD ["gunicorn", "--timeout 600", "--workers=5", "--threads=2", "-b 0.0.0.0:8000", "app:server"]
# CMD [ "python", "app.py"]