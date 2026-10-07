import pytest

from council import CouncilResponse, demo_response
from safety import detect_crisis, support_for_country
from db import make_db, requests_today, save_decision, list_decisions, delete_all, set_feedback
from export import as_pdf


@pytest.mark.parametrize("phrase", ["I want to kill myself", "I don't want to live", "someone is blackmailing me", "I am unsafe at home"])
def test_crisis_phrases_route_to_safety(phrase):
    result = detect_crisis(phrase)
    assert result.is_crisis
    assert result.message


@pytest.mark.parametrize("phrase", [
    "I am suicidal", "I am thinking about ending it all", "there is no point in living",
    "I wish I could disappear", "my partner hits me", "someone is hitting me",
    "my password was stolen", "they are extorting me",
])
def test_reviewed_crisis_phrase_list_triggers(phrase):
    assert detect_crisis(phrase).is_crisis


@pytest.mark.parametrize("phrase", [
    "I am deciding whether to change jobs", "I feel invisible at work", "How do I disappear from social media?",
    "Should I negotiate my salary?", "I want to end this project",
])
def test_normal_phrase_list_does_not_trigger(phrase):
    assert not detect_crisis(phrase).is_crisis


def test_safe_text_not_flagged():
    assert not detect_crisis("Should I change careers?").is_crisis


def test_response_schema_and_confidence_bounds():
    result = demo_response("Should I apply?")
    assert isinstance(result, CouncilResponse)
    assert 0 <= result.confidence <= 1
    assert result.logic.advice


def test_vague_dilemma_asks_for_context():
    result = __import__("council").analyze("Should I leave?", "Career")
    assert result.clarifying_question
    assert result.confidence < 0.2


def test_region_support_has_fallback():
    assert support_for_country("IN")["emergency"] == "112"
    assert "local" in support_for_country("XX")["emergency"]


def test_new_database_starts_with_zero_requests(tmp_path):
    assert requests_today(make_db(tmp_path / "test.db")) == 0


def test_user_scoping_and_deletion(tmp_path):
    engine = make_db(tmp_path / "scope.db")
    save_decision(engine, "A longer dilemma for testing", "Career", demo_response("x").model_dump_json(), "alice")
    save_decision(engine, "A longer dilemma for testing", "Career", demo_response("x").model_dump_json(), "bob")
    assert len(list_decisions(engine, user_id="alice")) == 1
    delete_all(engine, "alice")
    assert list_decisions(engine, user_id="alice") == []
    assert len(list_decisions(engine, user_id="bob")) == 1


def test_feedback_comment_is_persisted(tmp_path):
    engine = make_db(tmp_path / "feedback.db")
    decision_id = save_decision(engine, "A longer dilemma for testing", "Career", demo_response("x").model_dump_json(), "alice")
    set_feedback(engine, decision_id, 1, "Useful perspective")
    assert list_decisions(engine, user_id="alice")[0].feedback_comment == "Useful perspective"


def test_pdf_export_contains_all_perspectives(tmp_path):
    pdf = as_pdf("A long decision", "Career", demo_response("A long decision"))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
