FROM python:3-alpine
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
#ENV FLASK_APP=webhook.py
CMD ["python", "./web/webhook.py"]
