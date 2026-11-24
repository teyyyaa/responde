from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from broker.broker import Broker
from clients.messages import validate_report


class BrokerServer:
    def __init__(self, broker: Broker | None = None, host: str = "0.0.0.0", port: int = 8000):
        self.broker = broker or Broker()
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None

    def publish(self, body: dict) -> tuple[int, dict]:
        problem = validate_report(body)
        if problem:
            return 400, {"error": problem}
        topic = f"emergency/{str(body['incident_type']).lower()}"
        try:
            delivered, queued = self.broker.publish(topic, body)
        except Exception as exc:
            return 503, {"error": str(exc)}
        return 200, {
            "report_id": body["report_id"],
            "topic": topic,
            "delivered": delivered,
            "queued": queued,
        }

    def subscribe(self, body: dict) -> tuple[int, dict]:
        required = ("subscriber_id", "name", "topics")
        missing = [key for key in required if key not in body]
        if missing:
            return 400, {"error": f"missing fields: {', '.join(missing)}"}
        if not isinstance(body["topics"], list) or not all(
            isinstance(topic, str) for topic in body["topics"]
        ):
            return 400, {"error": "topics must be a list of strings"}
        subscriber_id = str(body["subscriber_id"])
        name = str(body["name"])
        topics = body["topics"]
        self.broker.register_subscriber(subscriber_id, name, topics, callback=None)
        return 200, {"subscriber_id": subscriber_id, "name": name, "topics": topics}

    def set_online(self, body: dict) -> tuple[int, dict]:
        if "subscriber_id" not in body or "online" not in body:
            return 400, {"error": "subscriber_id and online are required"}
        subscriber_id = str(body["subscriber_id"])
        online = body["online"]
        if not isinstance(online, bool):
            return 400, {"error": "online must be a boolean"}
        if subscriber_id not in self.broker.subscribers:
            return 404, {"error": "unknown subscriber"}
        self.broker.set_online(subscriber_id, online)
        return 200, {"subscriber_id": subscriber_id, "online": online}

    def acknowledge(self, body: dict, negative: bool = False) -> tuple[int, dict]:
        required = ("subscriber_id", "report_id")
        missing = [key for key in required if key not in body]
        if missing:
            return 400, {"error": f"missing fields: {', '.join(missing)}"}
        subscriber_id = str(body["subscriber_id"])
        report_id = str(body["report_id"])
        if negative:
            result = self.broker.nack(
                subscriber_id, report_id, str(body.get("reason", "Delivery failed"))
            )
            if result == "NOT_FOUND":
                return 404, {"error": "unknown delivery"}
            return 200, {"subscriber_id": subscriber_id, "report_id": report_id, "status": result}
        if not self.broker.ack(subscriber_id, report_id):
            return 404, {"error": "unknown delivery"}
        return 200, {"subscriber_id": subscriber_id, "report_id": report_id, "status": "ACK"}

    def respond(self, body: dict) -> tuple[int, dict]:
        required = ("subscriber_id", "report_id", "status")
        missing = [key for key in required if key not in body]
        if missing:
            return 400, {"error": f"missing fields: {', '.join(missing)}"}
        try:
            status = self.broker.update_status(
                str(body["subscriber_id"]), str(body["report_id"]), str(body["status"])
            )
        except ValueError as exc:
            return 404, {"error": str(exc)}
        return 200, {
            "subscriber_id": str(body["subscriber_id"]),
            "report_id": str(body["report_id"]),
            "status": status,
        }

    def run(self) -> None:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, status: int, payload: dict) -> None:
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
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("JSON body must be an object")
                return body

            def do_POST(self) -> None:
                try:
                    body = self._body()
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                    self._json(400, {"error": "invalid JSON object"})
                    return

                path = urlparse(self.path).path
                if path == "/publish":
                    result = server.publish(body)
                elif path == "/subscribe":
                    result = server.subscribe(body)
                elif path == "/online":
                    result = server.set_online(body)
                elif path == "/ack":
                    result = server.acknowledge(body)
                elif path == "/nack":
                    result = server.acknowledge(body, negative=True)
                elif path == "/respond":
                    result = server.respond(body)
                else:
                    result = (404, {"error": "not found"})
                self._json(*result)

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                path = parsed.path
                if path.startswith("/poll/"):
                    subscriber_id = unquote(path[len("/poll/"):])
                    result = (200, {"deliveries": server.broker.poll(subscriber_id)})
                elif path == "/subscribers":
                    result = (
                        200,
                        {
                            "subscribers": {
                                subscriber_id: {
                                    "name": item["name"],
                                    "topics": item["topics"],
                                    "online": item["online"],
                                }
                                for subscriber_id, item in server.broker.subscribers.items()
                            }
                        },
                    )
                elif path == "/events":
                    result = (200, {"events": server.broker.log})
                elif path == "/reports":
                    result = (200, {"reports": server.broker.storage.get_reports()})
                elif path == "/publisher-reports":
                    source = parse_qs(parsed.query).get("source", [""])[0]
                    result = (
                        200,
                        {"reports": server.broker.get_publisher_reports(source)},
                    )
                elif path == "/subscriber-reports":
                    subscriber_id = parse_qs(parsed.query).get("subscriber_id", [""])[0]
                    result = (
                        200,
                        {"reports": server.broker.get_subscriber_reports(subscriber_id)},
                    )
                else:
                    result = (404, {"error": "not found"})
                self._json(*result)

            def log_message(self, format: str, *args) -> None:
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._server.serve_forever()

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


def create_server(
    broker: Broker | None = None, host: str = "0.0.0.0", port: int = 8000
) -> BrokerServer:
    return BrokerServer(broker=broker, host=host, port=port)
