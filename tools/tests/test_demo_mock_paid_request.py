import pytest

from tools.demo_mock_paid_request import DemoFailure, _local_origin


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com",
        "http://user:password@127.0.0.1:8001",
    ],
)
def test_local_demo_refuses_non_loopback_or_credential_urls(url):
    with pytest.raises(DemoFailure):
        _local_origin(url)


def test_local_demo_accepts_loopback_gateway_urls():
    assert _local_origin("http://127.0.0.1:8001") == "http://127.0.0.1:8001"
    assert _local_origin("http://localhost:8000") == "http://localhost:8000"
