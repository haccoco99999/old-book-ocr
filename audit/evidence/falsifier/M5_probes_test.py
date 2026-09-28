"""Falsifier probes for evaluate_test / testeval, using the repo's own fixture (tmp logs, fake views). No GPU, no real data."""
import json, sys
sys.path.insert(0, "/home/huy/master/mlops/tests")
import pytest
from test_evaluate_test import env, views, fake_views, run, events, BASE, FINAL  # noqa: F401
from mlops import testeval


def test_rehearsal_on_dirty_training_tree_is_accepted_for_a_clean_test_access(env, views):
    # rehearsal: training + backend trees dirty (e.g. uncommitted skill 1.2 over 1.1) -> rehearsal allowed (strict=False)
    env["state"]["dirty_tracked_files"] = {"mlops": 0, "training": 4, "backend": 7}
    env["state"]["training_commit"], env["state"]["backend_commit"] = "t_OLD", "b_OLD"
    run(FINAL, views, rehearsal=True)
    # test access later: different training + backend commits, same mlops code_tree -> gate satisfied
    env["state"]["dirty_tracked_files"] = {"mlops": 0, "training": 0, "backend": 0}
    env["state"]["training_commit"], env["state"]["backend_commit"] = "t_NEW", "b_NEW"
    entry = run(FINAL, views)
    assert entry["event"] == "completed"
    started = [e for e in testeval.read_log(testeval.TEST_LOG) if e["event"] == "started"][0]
    assert "training_commit" not in started and "backend_commit" not in started   # not even recorded


def test_whitespace_rerun_reason_is_accepted(env, views):
    env["state"]["dirty_tracked_files"] = {"mlops": 0, "training": 0, "backend": 0}
    run(FINAL, views, rehearsal=True)
    run(FINAL, views)
    with pytest.raises(SystemExit):
        run(FINAL, views, reason="")          # empty string refused
    e = run(FINAL, views, reason=" ")          # a single space passes
    assert e["event"] == "completed"


def test_report_without_markup_key_never_aborts(env, monkeypatch):
    # a viet-ocr-eval 1.0 report has no health.markup_chars: check_report reads 0 and the limit-0 abort cannot fire
    p = env["tmp"] / "r.json"
    p.write_text(json.dumps({"protocol_version": "1.0", "overall": {"cer_micro": 0.01, "health": {}},
                             "pages": [{"page_id": "t/page_1"}]}))
    res = testeval.check_report(p, {"t/page_1"}, 0)
    assert res["markup_chars"] == 0 and res["protocol_version"] == "1.0"
