"""Route registration module for Ping Monitoring System."""

from flask import Flask

from .api_devices import api_devices_bp
from .api_ml import api_ml_bp
from .api_monitoring import api_monitoring_bp
from .api_settings import api_settings_bp
from .web import web_bp


def register_routes(app: Flask) -> None:
    """Register all modular web and API blueprints with the Flask app."""
    app.register_blueprint(web_bp)
    app.register_blueprint(api_devices_bp)
    app.register_blueprint(api_monitoring_bp)
    app.register_blueprint(api_ml_bp)
    app.register_blueprint(api_settings_bp)
