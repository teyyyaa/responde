from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from broker.broker import Broker
from clients.messages import validate_report


class ApiServer:
    def __init__(self, broker: Broker | None = None, host: str = "127.0.0.1", port: int = 8000):
        self.broker = broker or Broker()
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None

    def publish(self, body: dict) -> tuple[int, dict]:
        report = body
        problem = validate_report(report)
        if problem:
            return 400, {"error": problem}
        topic = f"emergency/{str(report['incident_type']).lower()}"
        try:
            delivered, queued = self.broker.publish(topic, report)
            return 200, {
                "report_id": report["report_id"],
                "topic": topic,
                "delivered": delivered,
                "queued": queued,
            }
        except Exception as exc:
            return 503, {"error": str(exc)}

    def subscribe(self, body: dict) -> tuple[int, dict]:
        required = ("subscriber_id", "name", "topics")
        missing = [key for key in required if key not in body]
        if missing:
            return 400, {"error": f"missing fields: {', '.join(missing)}"}
        subscriber_id = str(body["subscriber_id"])
        name = str(body["name"])
        topics = body["topics"]
        if not isinstance(topics, list):
            return 400, {"error": "topics must be a list"}
        callback = body.get("callback")
        if not callable(callback):
            callback = lambda topic, report: True
        self.broker.register_subscriber(subscriber_id, name, topics, callback)
        online = body.get("online", True)
        self.broker.set_online(subscriber_id, bool(online))
        return 200, {"subscriber_id": subscriber_id, "name": name, "topics": topics}

    def respond(self, body: dict) -> tuple[int, dict]:
        required = ("subscriber_id", "report_id", "status")
        missing = [key for key in required if key not in body]
        if missing:
            return 400, {"error": f"missing fields: {', '.join(missing)}"}
        try:
            status = self.broker.update_status(
                str(body["subscriber_id"]), str(body["report_id"]), str(body["status"])
            )
            return 200, {
                "subscriber_id": str(body["subscriber_id"]),
                "report_id": str(body["report_id"]),
                "status": status,
            }
        except ValueError as exc:
            return 404, {"error": str(exc)}

    def reports(self) -> tuple[int, dict]:
        return 200, {"reports": self.broker.storage.get_reports()}

    def run(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: dict):
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                if not length:
                    return {}
                return json.loads(self.rfile.read(length).decode("utf-8"))

            def do_POST(self):
                path = urlparse(self.path).path
                try:
                    body = self._body()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self._json(400, {"error": "invalid JSON"})
                    return
                if path == "/publish":
                    status, payload = api.publish(body)
                elif path == "/subscribe":
                    status, payload = api.subscribe(body)
                elif path == "/respond":
                    status, payload = api.respond(body)
                else:
                    status, payload = 404, {"error": "not found"}
                self._json(status, payload)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/reports":
                    status, payload = api.reports()
                else:
                    status, payload = 404, {"error": "not found"}
                self._json(status, payload)

            def log_message(self, format, *args):
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._server.serve_forever()

    def shutdown(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def create_app(broker: Broker | None = None, host: str = "127.0.0.1", port: int = 8000) -> ApiServer:
    return ApiServer(broker=broker, host=host, port=port)


app = create_app()


if __name__ == "__main__":
    app.run()