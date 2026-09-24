import hashlib

import yaml

from smb3_agent.beta_readiness import CONTRACT_PATH, MANIFEST_SCHEMA, inspect_beta


def manifest(tmp_path):
    evidence = tmp_path / "proof.txt"
    evidence.write_text("retained test evidence")
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    checks = {row["id"]: {"status": "pass", "classification": row["classification"],
                         "artifacts": [{"path": "proof.txt", "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}]}
              for stage, rows in contract["stages"].items() if stage.startswith("B2.") for row in rows}
    candidate = {"head": "abc", "source_sha256": "def"}
    value = {"schema_version": MANIFEST_SCHEMA, **candidate, "checks": checks,
             "owner_acceptance": None, "contract_sha256": hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()}
    return value, candidate


def test_b2_pass_is_b3_handoff_only_and_has_no_third_game_gate(tmp_path):
    value, candidate = manifest(tmp_path)
    result = inspect_beta(value, evidence_root=tmp_path, candidate=candidate)
    assert result["b2_complete"] and result["ready_for_b3"]
    assert not result["beta_ready"]
    assert result["remaining"]["B3"]
    assert result["owner_acceptance"] is None
    assert not result["third_game_onboarding_required"]


def test_fixtures_old_candidate_and_modified_evidence_cannot_supply_live_proof(tmp_path):
    value, candidate = manifest(tmp_path)
    value["checks"]["alternate_traversal"]["classification"] = "unit_integration_result"
    result = inspect_beta(value, evidence_root=tmp_path, candidate=candidate)
    assert result["first_unmet_b2_requirement"] == "B2.2: alternate_traversal"
    value, candidate = manifest(tmp_path)
    candidate["source_sha256"] = "changed"
    assert not inspect_beta(value, evidence_root=tmp_path, candidate=candidate)["ready_for_b3"]
    value, candidate = manifest(tmp_path)
    (tmp_path / "proof.txt").write_text("modified")
    assert not inspect_beta(value, evidence_root=tmp_path, candidate=candidate)["ready_for_b3"]


def test_b3_requires_every_classified_candidate_bound_check(tmp_path):
    value, candidate = manifest(tmp_path)
    contract = yaml.safe_load(CONTRACT_PATH.read_text())
    artifact = value['checks']['canonical_gate']['artifacts']
    for row in contract['stages']['B3']:
        value['checks'][row['id']] = {
            'status': 'pass', 'classification': row['classification'],
            'artifacts': artifact,
        }
    result = inspect_beta(value, evidence_root=tmp_path, candidate=candidate)
    assert result['b3_complete'] and result['ready_for_b4']
    assert not result['beta_ready']
    assert result['owner_acceptance'] is None
    for row in contract['stages']['B3']:
        record = value['checks'].pop(row['id'])
        result = inspect_beta(value, evidence_root=tmp_path, candidate=candidate)
        assert not result['b3_complete']
        assert result['first_unmet_b3_requirement'] == 'B3: ' + row['id']
        value['checks'][row['id']] = record
    value['checks']['live_watering']['classification'] = 'unit_integration_result'
    assert not inspect_beta(value, evidence_root=tmp_path, candidate=candidate)['ready_for_b4']
    value['checks']['live_watering']['classification'] = 'visible_live_result'
    candidate['source_sha256'] = 'different-candidate'
    assert not inspect_beta(value, evidence_root=tmp_path, candidate=candidate)['ready_for_b4']
