"""Main Flask Application Entrypoint for Ping Monitoring System."""

import os
from flask import Flask
from config import BASE_DIR, DEFAULT_HOST, DEFAULT_PORT
from monitoring import start_monitoring
from routes import register_routes


def create_app() -> Flask:
    """Application factory for Ping Monitoring System."""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Injected template globals
    @app.context_processor
    def inject_template_globals():
        return {
            "csrf_token": lambda: "",
        }

    # Register all modular blueprints
    register_routes(app)

    return app


app = create_app()

# Start background monitoring service on app startup (if not in test mode)
if not os.getenv("TESTING"):
    start_monitoring()


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("NETWORK_MONITOR_PORT", str(DEFAULT_PORT))))
    host = os.getenv("HOST", os.getenv("NETWORK_MONITOR_HOST", DEFAULT_HOST))
    print(f"Internal ICMP & ML Engine running for Laravel on {host}:{port}")
    app.run(debug=True, host=host, port=port)
