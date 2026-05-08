"""HTTP dispatch path tests using respx to mock httpx calls.

The router's HTTP transport is the default for every analyser shipped
in auto_analyser.config._DEFAULTS, but had no test coverage before
this file. Each test exercises one branch of Router._call_http.
"""

from pathlib import Path

import httpx
import pytest
import respx

from auto_analyser.config import AnalyserConfig, FamilyConfig
from auto_analyser.router import Router, RoutingError


def _make_router_with_http(tmp_path: Path) -> tuple[Router, Path]:
    """Build a Router whose 'records-analyser' analyser is HTTP-dispatched."""
    config = FamilyConfig(analysers={
        "records-analyser": AnalyserConfig(
            type="http",
            url="http://localhost:8003",
            formats=[".csv"],
        ),
    })
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("a,b\n1,2\n")
    return Router(config=config), csv_file


@respx.mock
def test_http_dispatch_returns_parsed_response_with_routed_to(tmp_path: Path):
    """Successful HTTP dispatch parses the JSON body and injects routed_to."""
    router, csv_file = _make_router_with_http(tmp_path)
    respx.post("http://localhost:8003/analyse").mock(
        return_value=httpx.Response(200, json={"format": "csv", "row_count": 1})
    )

    result = router.route(csv_file, analyser_name="records-analyser")

    assert result["format"] == "csv"
    assert result["row_count"] == 1
    assert result["routed_to"] == "records-analyser"


@respx.mock
def test_http_dispatch_non_2xx_raises_routing_error(tmp_path: Path):
    """Non-2xx HTTP response surfaces as RoutingError carrying the detail."""
    router, csv_file = _make_router_with_http(tmp_path)
    respx.post("http://localhost:8003/analyse").mock(
        return_value=httpx.Response(422, json={"detail": "Unsupported encoding"})
    )

    with pytest.raises(RoutingError, match="Unsupported encoding"):
        router.route(csv_file, analyser_name="records-analyser")


@respx.mock
def test_http_dispatch_connect_error_raises_routing_error(tmp_path: Path):
    """ConnectError ('service down') surfaces as RoutingError mentioning the URL."""
    router, csv_file = _make_router_with_http(tmp_path)
    respx.post("http://localhost:8003/analyse").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(RoutingError, match="localhost:8003"):
        router.route(csv_file, analyser_name="records-analyser")
