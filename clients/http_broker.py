"""HTTP transport adapter for connecting dashboard clients to a LAN broker."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class HttpBroker:
    polling = True

    def __init__(self, base_url: str, timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(detail).get("error", detail)
            except json.JSONDecodeError:
                message = detail or str(exc)
            raise RuntimeError(f"Broker returned HTTP {exc.code}: {message}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(f"Could not reach broker at {self.base_url}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Broker returned an invalid response")
        return payload

    def publish(self, topic: str, report: dict) -> tuple[list[str], list[str]]:
        result = self._request("POST", "/publish", report)
        return result["delivered"], result["queued"]

    def register_subscriber(
        self, subscriber_id: str, name: str, topics: list[str], callback=None
    ) -> None:
        self._request(
            "POST",
            "/subscribe",
            {"subscriber_id": subscriber_id, "name": name, "topics": topics},
        )

    def set_online(self, subscriber_id: str, online: bool) -> None:
        self._request(
            "POST", "/online", {"subscriber_id": subscriber_id, "online": online}
        )

    def poll(self, subscriber_id: str) -> list[dict]:
        result = self._request("GET", f"/poll/{quote(subscriber_id, safe='')}")
        return result["deliveries"]

    def ack(self, subscriber_id: str, report_id: str):
        self._request(
            "POST", "/ack", {"subscriber_id": subscriber_id, "report_id": report_id}
        )
        return True

    def nack(self, subscriber_id: str, report_id: str, reason: str = "Delivery failed"):
        result = self._request(
            "POST",
            "/nack",
            {
                "subscriber_id": subscriber_id,
                "report_id": report_id,
                "reason": reason,
            },
        )
        return result["status"]

    def update_status(self, subscriber_id: str, report_id: str, status: str):
        result = self._request(
            "POST",
            "/respond",
            {
                "subscriber_id": subscriber_id,
                "report_id": report_id,
                "status": status,
            },
        )
        return result["status"]

    def get_subscriber_reports(self, subscriber_id: str) -> list[dict]:
        result = self._request(
            "GET", f"/subscriber-reports?subscriber_id={quote(subscriber_id, safe='')}"
        )
        return result["reports"]

    def get_publisher_reports(self, source: str) -> list[dict]:
        result = self._request(
            "GET", f"/publisher-reports?source={quote(source, safe='')}"
        )
        return result["reports"]

    @property
    def subscribers(self) -> dict:
        return self._request("GET", "/subscribers")["subscribers"]

    @property
    def log(self) -> list[tuple]:
        return [tuple(item) for item in self._request("GET", "/events")["events"]]
