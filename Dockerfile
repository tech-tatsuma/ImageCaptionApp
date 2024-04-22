FROM python:3.10

ENV DEBIAN_FRONTEND=noninteractive
ENV LANGUAGE=en


# set working directory
RUN mkdir -p /usr/src/route
WORKDIR /usr/src/route
COPY requirements.txt /usr/src/route/requirements.txt

RUN pip install -r requirements.txt

COPY ./app /usr/src/route/app

CMD uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload