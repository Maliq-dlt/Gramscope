"""One runnable scientific contract check for the fresh synthetic context-tail study."""

from collections import Counter

from core.src.ngram import events
from extensions.experiments import context_tail_study as study


def test_source_split_pair_match_calibration_and_backoff():
    cases, split = study.construct(101)
    other, _ = study.construct(202)
    assert [len(split[name]) for name in study.GROUPS] == [120, 40, 80, 80]
    assert len(set().union(*map(set, split.values()))) == sum(study.GROUPS.values())
    assert cases == study.construct(101)[0]
    assert Counter(row["symbols"] for row in cases if row["partition"] == "train") != Counter(
        row["symbols"] for row in other if row["partition"] == "train"
    )
    assert len({len(row["symbols"]) for row in cases if row["partition"] == "train"}) > 10
    bank, model, selection = study.fit(cases)
    calibration = study.calibrate(cases, model)
    assert len(selection["trials"]) == 4
    assert all(len(scores) == 80 for scores in calibration.values())
    assert all(bank.raw[2][pair] >= 2 for pair in events(study.HARD, 2))
    group = [
        row
        for row in cases
        if row["partition"] == "test" and row["source_group"] == split["test"][0]
    ]
    normal = next(row["symbols"] for row in group if row["scenario"] == "paired_normal")
    hard = next(row["symbols"] for row in group if row["scenario"] == "hard_replacement")
    assert Counter(normal) == Counter(hard)
    assert Counter(events(normal, 2)) == Counter(events(hard, 2))
    assert Counter(events(normal, 3)) != Counter(events(hard, 3))
    assert all(pair in study.LEGAL_PAIRS for pair in events(normal, 2))
    assert all(pair in study.LEGAL_PAIRS for pair in events(hard, 2))
    dev = next(row["symbols"] for row in cases if row["partition"] == "dev")
    dev_score = study.case_scores(model, [dev])
    assert dev_score["targets"] == sum(dev_score[f"order_{n}"] for n in (1, 2, 3))
    assert sum(study.tail_score(model, ["Z"])[1].values()) == 2
    assert study.tail_score(model, ["Z"])[1].get("order_1", 0) >= 1
    assert sum(row["known_nohelmet_rule"] and not row["latent_novel"] for row in group) == 1
    assert study.conformal_p([1.0] * 80, 1.0) == 1
