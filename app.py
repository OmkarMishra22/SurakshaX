import os
import sys
import socket
import subprocess
import threading
import webbrowser
import logging
from flask import Flask, render_template, send_from_directory
import flask.cli

# Suppress Flask's red development-server warning banner in VS Code terminal
flask.cli.show_server_banner = lambda *args, **kwargs: None

from database.database import DB_PATH, init_db
from database.seed import seed_database
from routes.auth_routes import auth_bp
from routes.reports_routes import reports_bp
from routes.safety_gate_routes import safety_gate_bp
from routes.machines_routes import machines_bp
from routes.hse_routes import hse_bp
from routes.analytics_routes import analytics_bp
from routes.admin_routes import admin_bp

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static")
    )
    app.secret_key = "sifguard-sih2026-oil-india-secure-key"
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Initialize database and seed demo risk data if reports table is empty
    try:
        seed_database()
    except Exception:
        try:
            init_db()
        except Exception:
            pass

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(safety_gate_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(hse_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def index():
        from flask import request
        server_port = str(request.environ.get("SERVER_PORT", ""))
        host = str(request.host)
        is_worker = (
            request.environ.get("IS_WORKER_PORTAL") or
            server_port == "5001" or
            "5001" in host or
            request.args.get("portal") == "worker"
        )
        if is_worker:
            return render_template("worker.html")
        return render_template("index.html")

    @app.route("/worker")
    @app.route("/worker-portal")
    def worker_portal():
        return render_template("worker.html")

    return app

app = create_app()

class WorkerPortalMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        environ["IS_WORKER_PORTAL"] = True
        return self.wsgi_app(environ, start_response)

def _free_port_if_busy(port: int):
    """Automatically releases port if occupied by a previous background python process."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            if os.name == "nt":
                my_pid = os.getpid()
                cmd = (
                    f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                    f"Where-Object {{ $_.OwningProcess -ne {my_pid} -and $_.OwningProcess -gt 4 }} | "
                    f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
                )
                try:
                    subprocess.run(["powershell", "-NoProfile", "-Command", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                except Exception:
                    pass

if __name__ == "__main__":
    from werkzeug.serving import run_simple

    _free_port_if_busy(5000)
    _free_port_if_busy(5001)

    worker_wsgi_app = WorkerPortalMiddleware(app)

    def _listen(host, port, wsgi_target):
        try:
            run_simple(host, port, wsgi_target, threaded=True, use_reloader=False)
        except Exception:
            pass

    # Start Worker Portal on both IPv4 (0.0.0.0:5001) and IPv6 (::1:5001)
    threading.Thread(target=_listen, args=("0.0.0.0", 5001, worker_wsgi_app), daemon=True).start()
    threading.Thread(target=_listen, args=("::1", 5001, worker_wsgi_app), daemon=True).start()

    # Also bind IPv6 ::1:5000 alongside IPv4 0.0.0.0:5000
    threading.Thread(target=_listen, args=("::1", 5000, app), daemon=True).start()

    print("\n================================================================")
    print("  [SurakshaX] Server Running Successfully!")
    print("  Oil India Limited • SurakshaX Safety AI Platform")
    print("----------------------------------------------------------------")
    print("  -> Open in Browser (Main Portal):   http://localhost:5000")
    print("  -> Open in Browser (Worker Portal): http://localhost:5001")
    print("  -> Local Network IPv4:              http://127.0.0.1:5000")
    print("================================================================\n", flush=True)

    # Auto-open browser if not suppressed by env var
    if os.environ.get("SURAKSHAX_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open("http://localhost:5000")).start()

    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False, use_reloader=False)
