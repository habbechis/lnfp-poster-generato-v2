"""Local development entry point: ``python run.py``.

For production (Render) Gunicorn serves ``wsgi:app`` instead.
"""
import os

from app import create_app

application = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    application.run(host="0.0.0.0", port=port, debug=True)
