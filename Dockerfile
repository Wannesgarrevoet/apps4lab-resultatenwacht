FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY portaal_client.py resultaten.py mailer.py watcher.py ./

ENV STATE_FILE=/data/state.json
VOLUME ["/data"]

# Standaard: elk uur controleren. Overschrijf met een eigen commando indien nodig.
CMD ["python", "watcher.py", "--loop", "3600"]
