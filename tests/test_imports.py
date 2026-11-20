import socket
from io import BytesIO
from unittest.mock import Mock

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from jobevent import imports


def test_portfolio_import_removes_hidden_text(monkeypatch):
    monkeypatch.setattr(
        imports,
        "fetch",
        lambda _: (
            "<style>hidden</style><h1>프로젝트</h1><script>hidden</script><p>모집 서비스 개발</p>"
        ),
    )
    assert (
        imports.reference("https://portfolio.example/profile")
        == "프로젝트 모집 서비스 개발"
    )


def test_github_import_uses_public_profile_and_repos(monkeypatch):
    fetch = Mock(
        side_effect=[
            '{"bio":"public bio"}',
            '[{"name":"public-demo","language":"Python","description":"open tools"}]',
        ]
    )
    monkeypatch.setattr(imports, "fetch", fetch)
    result = imports.reference("https://github.com/example-user/")
    assert "public bio" in result and "public-demo (Python)" in result
    assert [c.args[0] for c in fetch.call_args_list] == [
        "https://api.github.com/users/example-user",
        "https://api.github.com/users/example-user/repos?sort=pushed&per_page=12",
    ]


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "::1", "10.2.3.4", "169.254.169.254", "224.0.0.1"]
)
def test_import_rejects_nonpublic_or_mixed_dns_answers(monkeypatch, ip):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(0, 0, 0, "", ("8.8.8.8", 443)), (0, 0, 0, "", (ip, 443))],
    )
    dial = Mock(side_effect=AssertionError("must not open a connection"))
    monkeypatch.setattr(socket, "create_connection", dial)
    with pytest.raises(ValueError):
        imports.fetch("https://portfolio.example")
    dial.assert_not_called()


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://portfolio.example",
        "https://user:pass@portfolio.example/",
        "https://portfolio.example:8443/",
    ],
)
def test_import_rejects_unsupported_url_before_dns(monkeypatch, url):
    dns = Mock(side_effect=AssertionError("unexpected DNS lookup"))
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    with pytest.raises(ValueError):
        imports.fetch(url)
    dns.assert_not_called()


def test_pdf_import_reads_a_real_text_document():
    writer = PdfWriter()
    page = writer.add_blank_page(200, 300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 240 Td (Career project) Tj ET")
    page[NameObject("/Contents")] = stream
    buf = BytesIO()
    writer.write(buf)
    assert imports.pdf_text(buf.getvalue()) == "Career project"


def test_invalid_pdf_reports_guidance_without_storing_document(service):
    with pytest.raises(ValueError, match="PDF"):
        service.change("/api/pdf", {"data": "YmFk"})
    assert not service.state()["profile"]
