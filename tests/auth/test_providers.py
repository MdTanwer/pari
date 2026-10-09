"""Provider lookup by id and by model name."""

import pytest

from pari.auth.providers import get_info, info_for_model


def test_get_info_normalizes_the_id_and_rejects_an_unknown_one():
    info = get_info(" OpenAI ")
    assert info.id == "openai"
    assert info.default_model == "gpt-4o"
    with pytest.raises(ValueError, match="Unknown provider 'nope'"):
        get_info("nope")


def test_info_for_model_matches_a_provider_id_or_a_model_prefix():
    assert info_for_model("openai").id == "openai"
    assert info_for_model("gpt-4o").id == "openai"
    assert info_for_model("o1-mini").id == "openai"
    routed = info_for_model("openrouter/openai/gpt-4o-mini")
    assert routed.id == "openrouter"
    assert info_for_model("not-a-model") is None
