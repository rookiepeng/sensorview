FROM python:3.8.6-slim-buster

RUN apt-get update
RUN apt-get install -yq --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libx11-xcb-dev \
    libxss1 \
    libasound2 \
    libxtst6 \
    xvfb

RUN rm -rf /var/lib/apt/lists/*


# Create a working directory.
WORKDIR /usr/src/app

# Install Python dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the codebase into the image
COPY . ./

# Finally, run gunicorn.
CMD ["gunicorn", "--workers=5", "--threads=2", "-b 0.0.0.0:8000", "app:server"]
# CMD [ "python", "app.py"]