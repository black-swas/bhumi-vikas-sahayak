import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.corpus import build_corpus  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402


@pytest.fixture(scope="session")
def built():
    """The corpus and index, built once for the whole test run."""
    return build_corpus()


@pytest.fixture(scope="session")
def corpus(built):
    return built[0]


@pytest.fixture(scope="session")
def index(built):
    return built[1]


@pytest.fixture()
def settings():
    return get_settings({"LLM_PROVIDER": "live", "AUDIT_SINK": "none"})


@pytest.fixture()
def make_pipeline(built, settings):
    """make_pipeline(understand=FakeLLM(...), compose=FakeLLM(...)) -> Pipeline."""
    corpus, index = built

    def factory(understand=None, compose=None, **kwargs):
        return Pipeline(corpus, index, settings, understand, compose, **kwargs)

    return factory
