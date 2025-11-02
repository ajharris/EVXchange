
# Heroku DATABASE_URL patch
import os
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    os.environ["DATABASE_URL"] = db_url.replace("postgres://", "postgresql://", 1)

from app import create_app
app = create_app()
