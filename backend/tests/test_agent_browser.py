import asyncio
import json

import pytest
from agent_fixtures import fixture_transport
from playwright.async_api import Error as BrowserError

from app.core.config import Settings
from app.engines.agent.actions import AgentAction
from app.engines.agent.browser import AgentScope, BrowserSession


def test_authorized_domain_validation_and_state_changing_links():
    scope = AgentScope("https://fixture.example/", ["docs.fixture.example"])
    assert scope.accept("https://docs.fixture.example/")
    for url in [
        "http://127.0.0.1/",
        "http://169.254.169.254/",
        "file:///etc/passwd",
        "https://evil.example/",
        "https://fixture.example/delete",
        "https://fixture.example/?token=secret",
    ]:
        with pytest.raises(ValueError):
            scope.accept(url)
    with pytest.raises(ValueError):
        AgentScope("https://fixture.example/", ["evil.example/path"])


def test_real_browser_observation_navigation_tools_and_network_blocks(tmp_path):
    async def scenario():
        calls = []
        browser = BrowserSession(
            "https://fixture.example/",
            [],
            Settings(agent_screenshot_dir=str(tmp_path)),
            "test",
            fixture_transport(calls),
        )
        try:
            await browser.start()
            await browser.navigate("https://fixture.example/")
            observation = await browser.observe()
            assert "Northstar" in observation["title"]
            pricing = next(e for e in observation["elements"] if e["name"] == "Plans and costs")
            stale = pricing["element_id"]
            await browser.execute(
                AgentAction(action="click", element_id=stale, reason="Open observed link")
            )
            observation = await browser.observe()
            assert "$12" in observation["visible_text"]
            with pytest.raises(ValueError, match="latest observation"):
                await browser.execute(AgentAction(action="click", element_id=stale, reason="Stale"))
            await browser.execute(AgentAction(action="go_back", reason="Return to homepage"))
            observation = await browser.observe()
            search = next(e for e in observation["elements"] if e["tag"] == "input")
            await browser.execute(
                AgentAction(
                    action="fill",
                    element_id=search["element_id"],
                    value="test",
                    reason="Inspect search",
                )
            )
            await browser.execute(
                AgentAction(action="scroll", direction="down", reason="Read below")
            )
            await browser.navigate("/join.html")
            observation = await browser.observe()
            assert "fixture-private-password" not in json.dumps(observation)
            assert "fixture-secret@example.com" not in json.dumps(observation)
            submit = next(e for e in observation["elements"] if e["name"] == "Create account")
            with pytest.raises(ValueError, match="blocked"):
                await browser.execute(
                    AgentAction(
                        action="click", element_id=submit["element_id"], reason="Submit forbidden"
                    )
                )
            email = next(e for e in observation["elements"] if e["type"] == "email")
            with pytest.raises(ValueError):
                await browser.execute(
                    AgentAction(
                        action="fill",
                        element_id=email["element_id"],
                        value="a@b.com",
                        reason="Unsafe",
                    )
                )
            select = next(e for e in observation["elements"] if e["tag"] == "select")
            await browser.execute(
                AgentAction(
                    action="select_option",
                    element_id=select["element_id"],
                    value="large",
                    reason="Inspect choices",
                )
            )
            assert await browser.screenshot(1)
            # Website JS cannot bypass the gateway with POST, direct IP subresources or WebSockets.
            await browser.page.evaluate("""async () => {try {await fetch('/account/create',{method:'POST',body:'forbidden'})}catch{};
                const image=new Image();image.src='http://169.254.169.254/latest/meta-data/';
                try {new WebSocket('ws://127.0.0.1:9999')}catch{};
                return typeof RTCPeerConnection;}""")
            await browser.page.evaluate("""async () => await new Promise(resolve => {
                const image = new Image(); image.onload = resolve; image.onerror = resolve;
                image.src='/delete'; document.body.appendChild(image);
            })""")
            assert all(method == "GET" and "fixture.example" in url for method, url in calls)
            assert browser.blocked_requests >= 1
        finally:
            await browser.close()
        assert browser.closed

    asyncio.run(scenario())


def test_browser_fallback_proxy_denies_direct_loopback_connections():
    async def scenario():
        connections = []

        async def private_server(reader, writer):
            connections.append(True)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nsecret")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(private_server, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        browser = BrowserSession(
            "https://fixture.example/",
            [],
            Settings(agent_screenshots=False),
            "fallback",
            fixture_transport(),
        )
        try:
            await browser.start()
            # Deliberately remove the gateway: Chromium must still not connect directly.
            await browser.context.unroute("**/*")
            try:
                response = await browser.page.goto(
                    f"http://127.0.0.1:{port}/", wait_until="domcontentloaded"
                )
            except BrowserError as exc:
                assert "ERR_PROXY_CONNECTION_FAILED" in str(exc)
            else:
                assert response.status == 403
                assert "secret" not in await browser.page.content()
            assert connections == []
        finally:
            await browser.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_prompt_injection_action_cannot_escape_browser_permissions():
    from app.engines.agent.runner import AgentRunner

    class InjectedModel:
        async def generate_action(self, messages):
            return AgentAction(
                action="navigate",
                url="http://169.254.169.254/latest/meta-data/",
                reason="Untrusted page requested metadata access",
            )

        async def close(self):
            pass

    async def scenario():
        calls = []
        settings = Settings(agent_screenshots=False)
        browser = BrowserSession(
            "https://fixture.example/", [], settings, "injection", fixture_transport(calls)
        )
        runner = AgentRunner(browser, InjectedModel(), settings)
        rows = []
        result = await runner.run("Find pricing", "https://fixture.example/", rows.append)
        assert result.outcome == "FAILED"
        assert runner.metrics["invalid_actions"] == 1
        assert browser.closed
        assert not browser.browser.is_connected()
        assert all("169.254.169.254" not in url for _, url in calls)
        assert all(row["error_message"] for row in rows[1:])

    asyncio.run(scenario())
