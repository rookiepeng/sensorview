# SensorView

<img src="./assets/sensorview_logo.svg" alt="logo" width="200"/>

A lightweight sensor data visualization and analysis tool.

## Screenshot

![](./assets/screenshot.png)

## Features

### 3D View and Filtering

![](./assets/3d.gif)

### 2D View and Filtering

![](./assets/2d.gif)


## Dependence

### Python modules

- dash
- dash-daq
- dash-bootstrap-components
- gunicorn
- flask
- numpy
- pandas
- redis
- kaleido

### [Redis](https://redis.io/)

## Usage

### Local debug

Save data as the `.pkl` files under `./data` directory. See `./data/Example`.

Put the `config.json` in the same directory, and sepcify the `columns` of the data in `config.json`. Check `./data/Example/config.json`.

> `redis-server`
> `python app.py`

- Open `http://127.0.0.1:8050/`

### Docker

> `docker pull redis`
> `docker pull rookeiepng/sensorview`
> `docker run --name redis -d redis`
> `docker run -it -p 8000:8000 -v <path/to/your/data>:/usr/src/app/data --link redis:redis rookiepeng/sensorview`

- Open `http://127.0.0.1:8000/`