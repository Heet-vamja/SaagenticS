from pathlib import Path

import httpx

ROOT = Path(__file__).parent / "fixtures" / "agent_site"


def fixture_transport(calls=None):
    def serve(request):
        if calls is not None:
            calls.append((request.method, str(request.url)))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, stream=httpx.ByteStream(b"User-agent: *\nAllow: /"))
        path = ROOT / (request.url.path.lstrip("/") or "index.html")
        if path.parent != ROOT or not path.is_file():
            return httpx.Response(404, stream=httpx.ByteStream(b"missing"))
        return httpx.Response(
            200, headers={"content-type": "text/html"}, stream=httpx.ByteStream(path.read_bytes())
        )

    return httpx.MockTransport(serve)
