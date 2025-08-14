# Import required Flask modules and configuration
from flask import Flask, request, g
import logging
import time
import uuid
import sys
from config import settings
from routes.api import api_bp


def create_app() -> Flask:
    # Create and configure the Flask application
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = settings.JSON_SORT_KEYS

    # Set up logging system for debugging
    _configure_logging(app)
    
    # Register main API blueprint under /api/v1 prefix
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.logger.debug("Registered blueprint 'api_bp' at /api/v1")
    print("[INIT] Registered blueprint 'api_bp' at /api/v1", flush=True)

    # Add request tracking and timing middleware
    _setup_request_middleware(app)

    @app.route("/")
    def index():
        # Health check endpoint
        return "<h1>Event & Speaker Finder Microservice</h1>"

    return app


def _configure_logging(app: Flask) -> None:
    # Set up logging configuration for the microservice
    log_level = logging.DEBUG if getattr(settings, "DEBUG", False) else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s %(levelname)s %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],  # Send logs to stdout for container compatibility
    )
    app.logger.setLevel(log_level)
    logging.getLogger('werkzeug').setLevel(log_level)

    app.logger.debug(
        "Initializing application with settings: host=%s port=%s debug=%s",
        getattr(settings, "HOST", "0.0.0.0"), getattr(settings, "PORT", ""), getattr(settings, "DEBUG", False)
    )
    print(f"[INIT] host={getattr(settings, 'HOST', '0.0.0.0')} port={getattr(settings, 'PORT', '')} debug={getattr(settings, 'DEBUG', False)}", flush=True)


def _setup_request_middleware(app: Flask) -> None:
    # Add middleware for request tracking, timing, and debugging
    
    @app.before_request
    def _before_request():
        # Log incoming requests and assign correlation ID
        # Create unique ID for tracking this request through logs
        g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        g._start_time = time.perf_counter()

        # Get request body preview for debugging (limit size to avoid memory issues)
        body_preview = ""
        try:
            raw = request.get_data(cache=True, as_text=True) or ""
            body_preview = (raw[:500] + "…") if len(raw) > 500 else raw
        except Exception:
            body_preview = "<unreadable>"

        app.logger.debug(
            "[%s] -> %s %s args=%s json=%s body=%s remote=%s",
            g.request_id,
            request.method,
            request.path,
            dict(request.args),
            request.get_json(silent=True),
            body_preview,
            request.remote_addr,
        )
        print(f"[REQ {g.request_id}] -> {request.method} {request.path} args={dict(request.args)} json={request.get_json(silent=True)} remote={request.remote_addr}", flush=True)

    @app.after_request
    def _after_request(response):
        # Log response details with timing
        duration_ms = None
        if hasattr(g, "_start_time"):
            duration_ms = round((time.perf_counter() - g._start_time) * 1000, 2)

        size = response.calculate_content_length() or 0
        app.logger.debug(
            "[%s] <- %s %sB in %sms",
            getattr(g, 'request_id', '-'),
            response.status_code,
            size,
            duration_ms if duration_ms is not None else "?",
        )
        print(f"[REQ {getattr(g, 'request_id', '-')} ] <- {response.status_code} {size}B in {duration_ms if duration_ms is not None else '?'}ms", flush=True)

        # Add correlation and timing headers for monitoring
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '')
        if duration_ms is not None:
            response.headers['X-Response-Time-ms'] = str(duration_ms)
        return response

    @app.teardown_request
    def _teardown_request(error=None):
        # Handle request teardown and errors
        if error is not None:
            app.logger.exception("[%s] Teardown with error: %s", getattr(g, 'request_id', '-'), error)


if __name__ == "__main__":
    # Run the microservice in development mode
    app = create_app()
    app.run(host=settings.HOST, port=settings.PORT, debug=settings.DEBUG)
