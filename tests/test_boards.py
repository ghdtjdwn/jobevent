import json

import pytest

from jobevent import sources
from jobevent.pipeline import Failure


def test_greenhouse_keeps_current_individual_urls(monkeypatch):
    requests = []

    def fetch(url):
        requests.append(url)
        return json.dumps(
            {
                "jobs": [
                    {
                        "absolute_url": "https://jobs.example/1",
                        "title": "Engineer",
                        "location": {"name": "Seoul"},
                    }
                ]
            }
        )

    monkeypatch.setattr(sources, "fetch", fetch)
    notes, urls = sources.board({"source": "greenhouse", "board": "sample"})
    assert requests == ["https://boards-api.greenhouse.io/v1/boards/sample/jobs"]
    assert urls == ["https://jobs.example/1"] and "Seoul" in notes


@pytest.mark.parametrize(
    "kind,domain", [("lever", "api.lever.co"), ("lever-eu", "api.eu.lever.co")]
)
def test_lever_valid_source(kind, domain, monkeypatch):
    def fetch(url):
        assert url.startswith(f"https://{domain}/v0/postings/example?")
        return json.dumps([{"hostedUrl": "https://jobs.example/one", "text": "Intern"}])

    monkeypatch.setattr(sources, "fetch", fetch)
    assert sources.board({"source": kind, "board": "example"})[1] == [
        "https://jobs.example/one"
    ]


def test_malformed_board_not_treated_as_empty(monkeypatch):
    monkeypatch.setattr(sources, "fetch", lambda url: "{}")
    with pytest.raises(Failure):
        sources.board({"source": "greenhouse", "board": "gone"})
