# Builds the backend for Google Cloud Run.
#
# WHY THE BUILD CONTEXT IS THE REPO ROOT, NOT backend/:
#   query_engine.py expects the database at ../data/formground.db
#   relative to itself, so this image needs backend/ and data/ side by
#   side, exactly like they are in the repo - not just backend/ copied
#   in on its own.
#
# HOW THE DATABASE GETS INTO THE IMAGE:
#   Phase 1 scale (a few thousand rows) doesn't need a real database
#   service or persistent volume - the SQLite file is just baked into
#   the image at build time, same as the code. That means the live data
#   only updates when this image gets rebuilt and redeployed, which is
#   why redeploying after each weekly scrape (see .github/workflows/
#   scrape.yml) matters - see the README for how to trigger that.

FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY data/ data/

WORKDIR /app/backend

# Cloud Run sets $PORT itself (usually 8080) - the app has to listen on
# whatever value that is, not a hardcoded port.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
