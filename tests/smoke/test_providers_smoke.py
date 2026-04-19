from modelito.openai import OpenAIProvider
from modelito.ollama import OllamaProvider
import os
import sys
import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)




def test_openai_provider_summarize_fallback():
    p = OpenAIProvider()
    res = p.summarize([{"role": "user", "content": "hello"}])
    assert isinstance(res, str)


def test_ollama_provider_summarize_fallback():
    p = OllamaProvider()
    res = p.summarize([{"role": "user", "content": "hey"}])
    assert isinstance(res, str)


def test_providers_list_models_do_not_error():
    p1 = OpenAIProvider()
    assert isinstance(p1.list_models(), list)
    p2 = OllamaProvider()
    assert isinstance(p2.list_models(), list)
