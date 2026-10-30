# Minecraft interpretation tests

`tests/data/minecraft-model-selection.json` contains 24 synthetic selection cases
for mapping questions to authoritative application facts. Cases include compound
questions, negation and references to prior user messages. Each case identifies a
source span and expected topics; review labels are kept outside model inputs.

`minecraft_grounding.py` constructs the evidence context. The offline integrity
test checks source offsets, unique case IDs, topic membership and the context-size
bound. It does not call a provider, compare models or establish answer quality.

```bash
.venv/bin/python -m pytest -q tests/test_minecraft_model_evaluation_cases.py tests/test_minecraft_grounding.py
```

Keep fixtures synthetic and preserve the distinction between current observations,
historical records and unknown facts. A selected fact can be true but irrelevant
to the question. See [known limitations](known-limitations.md) and
[provider configuration](ai-provider.md). No automated model-comparison or model
promotion runner is supplied.
