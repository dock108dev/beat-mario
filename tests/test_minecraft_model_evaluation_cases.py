"""Offline integrity of the proposed screen; no model or world is opened."""
import json
from pathlib import Path

from smb3_agent.minecraft_grounding import question_context


def test_fixed_selection_cases_have_source_provenance_and_separate_review_labels():
    fixture = json.loads((Path(__file__).parent/'data/minecraft-model-selection.json').read_text())
    cases = fixture['cases']
    assert len(cases) == len({case['id'] for case in cases}) == 24
    for case in cases:
        span = case['focus_span']
        assert case['source_question'][span['start']:span['end']] == span['text']
        state = fixture['states'][case['state']]
        inputs = question_context({'request': span['text'], **state,
                                   'recent_conversation': [{'role': 'user', 'text': text} for text in case['prior_user_messages']]})
        assert 'review_only' not in inputs
        required = set(case['review_only']['required_topics'])
        allowed = set(case['review_only']['allowed_topics'])
        assert required and required <= allowed <= set(inputs['evidence'])
        assert len(json.dumps(inputs)) < 32000
    assert any(not c['include_source_question'] for c in cases)
    assert any(c['include_source_question'] for c in cases)
