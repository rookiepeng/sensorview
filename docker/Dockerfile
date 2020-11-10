FROM python:3.8.6-slim-buster

# Create a working directory.
RUN mkdir app
WORKDIR app

RUN ls
RUN ls ..

# Install Python dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the codebase into the image
COPY . ./

RUN ls

# Finally, run gunicorn.
CMD [ "gunicorn", "--workers=5", "--threads=1", "-b 0.0.0.0:8000", "app:server"]