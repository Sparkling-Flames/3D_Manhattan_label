import json
import os
import datetime
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import sys

# Directory name (relative to script) where daily logs will be stored.
# Can be overridden by setting the environment variable ACTIVE_LOG_DIR.
LOG_DIR_NAME = os.environ.get("ACTIVE_LOG_DIR", "active_logs")

# Optional shared-secret to protect /log_time from public abuse.
# If unset/empty, token validation is disabled (backward compatible).
LOG_TOKEN = os.environ.get("HOHONET_LOG_TOKEN", "")

# Bind/port can be overridden to fit different deployments.
# Defaults keep backward compatibility.
BIND_HOST = os.environ.get("CORS_SERVER_BIND", "0.0.0.0")
PORT = int(os.environ.get("CORS_SERVER_PORT", "8001"))

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Note: CORS headers are now handled by nginx proxy (nginx_fixed.conf).
        # We only send Cache-Control here to ensure fresh data.
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        return super(CORSRequestHandler, self).end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path == '/log_time':
            # Token check (optional)
            if LOG_TOKEN:
                got = self.headers.get('X-HOHONET-TOKEN', '')
                if got != LOG_TOKEN:
                    self.send_response(403)
                    self.send_header('Content-Type', 'application/json')
                    # Note: CORS headers are handled by nginx proxy, don't send here to avoid duplication
                    self.end_headers()
                    self.wfile.write(b'{"status":"forbidden"}')
                    return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"bad_request"}')
                return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                # v0.21: Add server-side timestamp for audit trail
                data['server_received_at'] = datetime.datetime.now().isoformat()
                
                # Build logs directory and daily filename
                # Use project root (one level above the 'tools' directory)
                # i.e. repo_root/active_logs
                base_dir = Path(__file__).resolve().parent.parent
                logs_dir = base_dir / LOG_DIR_NAME
                logs_dir.mkdir(parents=True, exist_ok=True)

                today = datetime.datetime.now().strftime("%Y-%m-%d")
                log_path = logs_dir / f"active_times_{today}.jsonl"

                # Append to daily log file inside logs_dir
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(data) + "\n")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                # Note: CORS headers are handled by nginx proxy, don't send here to avoid duplication
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
                print(f"Logged time for task {data.get('task_id')} (Project {data.get('project_id', 'N/A')}): {data.get('active_seconds')}s -> {log_path}")
            except Exception as e:
                print(f"Error logging time: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status":"error"}')
        else:
            self.send_error(404, "File not found")

if __name__ == '__main__':
    print(f"Starting CORS-enabled HTTP server on http://{BIND_HOST}:{PORT} ...")
    print(f"Serving directory: {sys.path[0]}")
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / LOG_DIR_NAME
    print(f"Active logs directory: {logs_dir}")
    httpd = HTTPServer((BIND_HOST, PORT), CORSRequestHandler)
    httpd.serve_forever()
