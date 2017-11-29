FROM ubuntu:latest
RUN apt-get update -y && apt-get install -y python-pip python-dev build-essential && pip install --upgrade pip
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT [ "python" ]
WORKDIR /code/web
CMD ["webhook.py"]
