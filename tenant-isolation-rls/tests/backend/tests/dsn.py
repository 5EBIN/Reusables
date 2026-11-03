"""Database DSNs for tests. SV_DB selects the database (parallel worktrees each use their own); explicit env URLs win."""
import os

DB = os.environ.get("SV_DB", "app")
OWNER = os.environ.get("MIGRATION_DATABASE_URL", f"postgresql://<user>:<password>@127.0.0.1:5432/{DB}")
API = os.environ.get("DATABASE_URL", f"postgresql://<user>:<password>@127.0.0.1:5432/{DB}")
