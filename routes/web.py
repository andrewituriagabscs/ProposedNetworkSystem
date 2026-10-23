"""Web page routes for Ping Monitoring System."""

from flask import Blueprint, current_app, redirect, render_template, send_from_directory, url_for
from dashboard import get_dashboard_data
from monitoring import get_building_name

web_bp = Blueprint("web", __name__)


def _render_page(active_view: str):
    """Helper to assemble dashboard data and render template with active view."""
    data = get_dashboard_data()
    data["building_name"] = get_building_name()
    data["active_view"] = active_view
    return render_template("dashboard.html", **data)


@web_bp.route("/")
def index():
    return redirect(url_for("web.dashboard"))


@web_bp.route("/dashboard")
def dashboard():
    return _render_page("dashboard")


@web_bp.route("/ping")
def ping():
    return _render_page("ping")


@web_bp.route("/monitor")
def monitor():
    return redirect(url_for("web.ping"))


@web_bp.route("/alerts")
def alerts():
    return _render_page("alerts")


@web_bp.route("/records")
def records():
    return _render_page("records")


@web_bp.route("/reports")
@web_bp.route("/ping-records")
def reports_alias():
    return redirect(url_for("web.records"))


@web_bp.route("/ml-insights")
def ml_insights():
    return _render_page("ml-insights")


@web_bp.route("/settings")
def settings():
    return _render_page("settings")


@web_bp.route("/about")
def about():
    return _render_page("about")


@web_bp.route("/style.css")
def style_css():
    """Compatibility route for root /style.css requests."""
    return send_from_directory(current_app.static_folder, "style.css")
