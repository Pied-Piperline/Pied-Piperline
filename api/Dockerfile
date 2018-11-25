FROM python:3.7.0-slim-stretch

ADD . /code/
WORKDIR /code

RUN pip install --upgrade pip && pip install -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--reload", "--keyfile", "/etc/letsencrypt/live/pied-piperline.ml/fullchain.pem", "--certfile", "/etc/letsencrypt/live/pied-piperline.ml/fullchain.pem","api:init_app()"]