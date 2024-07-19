FROM python:3.10
WORKDIR /app
COPY . /app/
RUN pip3 install -r requirements.txt
CMD gunicorn app:app & python3 bot.py
