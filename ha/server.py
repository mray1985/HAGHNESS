"""HA Tax Software — local HTTP server.

Standard library only. No Flask, no FastAPI, no pip install. Bind to loopback
by default so the tool is not exposed to the network.

Routes
  GET  /                       the AIM-style client
  GET  /<static>               files from web/
  GET  /api/health             liveness + version
  GET  /api/attestation        full limited-status + coverage + checklist
  GET  /api/provenance         per-year citations and verification state
  GET  /api/years              available tax years
  GET  /api/brackets?year&status
  POST /api/calculate          federal return
  POST /api/state              state return attempt
  GET  /api/states             all 50 + DC with computable flags
  GET  /api/state/<code>       one jurisdiction, with refusal reason
  POST /api/chat               assistant turn
  GET  /api/chat/cards         knowledge base inventory
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ha.ai import Assistant                     # noqa: E402
from ha.compliance import (                     # noqa: E402
    DISCLAIMER_FULL,
    DISCLAIMER_SHORT,
    attestation_payload,
    environment,
    rule_provenance,
    state_coverage,
)
from ha.engine import federal as fed             # noqa: E402
from ha.engine import states as state_engine     # noqa: E402
from ha.rules import FILING_STATUS_LABELS, available_years  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
from ha.ai.library import TaxLibrary
ASSISTANT = Assistant(TaxLibrary(ROOT/'.connected-local/tax-library/library.sqlite3'))

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".wav": "audio/wav",
    ".ico": "image/x-icon",
}

#: Refuse to echo arbitrary filesystem paths out of web/.
_MAX_STATIC_BYTES = 4 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "HAGHNESS"
    sys_version = ""

    # -- plumbing --------------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[haghness] %s\n" % (fmt % args))

    def _send_json(self, payload, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > _MAX_STATIC_BYTES:
            return {}
        try:
            value=json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value,dict):raise ValueError('JSON object required')
            return value
        except (ValueError, UnicodeDecodeError):
            raise ValueError('Valid JSON object required')

    def _static(self, rel: str) -> None:
        target = (WEB / rel.lstrip("/")).resolve()
        try:
            target.relative_to(WEB.resolve())
        except ValueError:
            self._send_text("forbidden", 403)
            return
        if not target.is_file():
            self._send_text("not found", 404)
            return
        body = target.read_bytes()
        if len(body) > _MAX_STATIC_BYTES:
            self._send_text("too large", 413)
            return
        self.send_response(200)
        self.send_header("Content-Type", _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    # -- routing ---------------------------------------------------------
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route in ("/", "/home", "/home.html"):
            return self._static("home.html")
        if route in ("/index.html", "/tax"):
            return self._static("index.html")
        if route.startswith("/api/"):
            return self._api_get(route, query)
        if route == "/favicon.ico":
            return self._send_text("", 404)
        return self._static(route)

    def do_POST(self) -> None:
        try:
            return self._post()
        except (ValueError,TypeError,KeyError):
            return self._send_json({'error':'Check the entered values and request format'},400)

    def _post(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/calculate":
            return self._api_calculate()
        if route == "/api/state":
            return self._api_state()
        if route == "/api/chat":
            return self._api_chat()
        return self._send_json({"error": "unknown route", "route": route}, 404)

    # -- API: GET --------------------------------------------------------
    def _api_get(self, route: str, query: dict) -> None:
        if route == "/api/health":
            return self._send_json({
                "ok": True,
                "disclaimer_short": DISCLAIMER_SHORT,
                **environment(),
            })

        if route == "/api/attestation":
            return self._send_json({
                **attestation_payload(),
                "coverage_detail": state_coverage(),
            })

        if route == "/api/provenance":
            return self._send_json(rule_provenance())

        if route == "/api/years":
            return self._send_json({
                "years": available_years(),
                "statuses": FILING_STATUS_LABELS,
            })

        if route == "/api/brackets":
            year = (query.get("year") or ["2025"])[0]
            status = (query.get("status") or ["single"])[0]
            try:
                return self._send_json(fed.explain_brackets(year, status))
            except (KeyError, ValueError) as exc:
                return self._send_json({"error": str(exc)}, 400)

        if route == "/api/states":
            return self._send_json({
                "jurisdictions": state_engine.list_jurisdictions(),
                "coverage": state_coverage(),
            })

        if route.startswith("/api/state/"):
            code = route.rsplit("/", 1)[-1].upper()
            try:
                return self._send_json(state_engine.detail(code))
            except KeyError as exc:
                return self._send_json({"error": str(exc)}, 404)

        if route == "/api/chat/cards":
            from ha.ai.kb import CARDS
            return self._send_json({
                "count": len(CARDS),
                "cards": [
                    {"id": c["id"], "topic": c["topic"], "verified": c.get("verified", False),
                     "citation": c["citation"]}
                    for c in CARDS
                ],
            })

        if route == "/api/disclaimer":
            return self._send_text(DISCLAIMER_FULL)

        return self._send_json({"error": "unknown route", "route": route}, 404)

    # -- API: POST -------------------------------------------------------
    def _api_calculate(self) -> None:
        data = self._body()
        year = data.get("tax_year", "2025")
        status = data.get("filing_status", "single")
        if data.get("agi") in (None, ""):
            return self._send_json({
                "error": "agi is required",
                "why": "AGI is deliberately an input, not a computation. This engine "
                       "does not derive AGI from W-2s, 1099s, or Schedule 1 items.",
            }, 400)
        try:
            result = fed.compute(
                year,
                status,
                data["agi"],
                net_capital_gain=data.get("net_capital_gain", 0) or 0,
                qualifying_children=int(data.get("qualifying_children", 0) or 0),
                investment_income=data.get("investment_income", 0) or 0,
                earned_income=data.get("earned_income"),
            )
        except (KeyError, ValueError) as exc:
            return self._send_json({"error": str(exc)}, 400)
        return self._send_json({**result, "disclaimer_short": DISCLAIMER_SHORT})

    def _api_state(self) -> None:
        data = self._body()
        code = data.get("jurisdiction")
        if not code:
            return self._send_json({"error": "jurisdiction is required"}, 400)
        try:
            result = state_engine.compute(
                code,
                tax_year=data.get("tax_year", "2025"),
                filing_status=data.get("filing_status", "single"),
                agi=data.get("agi", 0) or 0,
                wage_income=data.get("wage_income"),
                interest_income=data.get("interest_income", 0) or 0,
                dividend_income=data.get("dividend_income", 0) or 0,
            )
        except KeyError as exc:
            return self._send_json({"error": str(exc)}, 404)
        return self._send_json(result)

    def _api_chat(self) -> None:
        data = self._body()
        question=data.get('question','')
        if not isinstance(question,str) or not isinstance(data.get('context',{}),dict):
            raise ValueError('Text question and object context required')
        question=question.strip()
        if not question:
            return self._send_json({"error": "question is required"}, 400)
        try:
            reply = ASSISTANT.ask(question, context=data.get("context") or {})
        except (KeyError, ValueError) as exc:
            return self._send_json({"error": str(exc)}, 400)
        return self._send_json(reply)


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    if not WEB.is_dir():
        raise SystemExit(f"web/ directory not found at {WEB}")
    server = ThreadingHTTPServer((host, port), Handler)
    print("=" * 68)
    print(f"  HAGHNESS  v{environment()['version']}")
    print("=" * 68)
    print(f"  UI        http://{host}:{port}/")
    print(f"  API       http://{host}:{port}/api/health")
    print(f"  Bound to  {host} (loopback only — not reachable from the network)")
    print()
    print(f"  {DISCLAIMER_SHORT}")
    print("  No tax year is human-verified yet, so every return the engine")
    print("  produces is reported as may_prepare_return=false. That is the")
    print("  intended state until you record a check in ha/rules/verification.json.")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  shutting down")
        server.shutdown()


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    main(host, port)
