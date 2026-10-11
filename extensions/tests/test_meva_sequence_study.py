"""Runnable checks for MEVA interval semantics and mapped predictive scoring."""

import math

from extensions.experiments.meva_sequence_study import clip_tokens, models, score_cases
from extensions.src.models import CountBank


def test_bridged_overlap_is_not_false_cooccurrence():
    activities = [
        (1, "Open_Trunk", 1080, 1170),
        (2, "Load_Vehicle", 1150, 1236),
        (3, "Close_Trunk", 1221, 1278),
        (4, "Open_Trunk", 1090, 1100),  # unchanged active state must collapse
    ]
    record = {
        "activities": [
            {"activity_id": identity, "labels": {label: 1.0}, "intervals": [[start, end]]}
            for identity, label, start, end in activities
        ],
        "actor_sequences": [
            {
                "actor_id": identity,
                "events": [
                    {
                        "activity_id": identity,
                        "labels": {label: 1.0},
                        "start_frame": start,
                        "end_frame": end,
                    }
                ],
            }
            for identity, label, start, end in activities
        ],
    }
    tokens, quality = clip_tokens(record)
    assert tokens == [
        '["Open_Trunk"]',
        '["Load_Vehicle","Open_Trunk"]',
        '["Load_Vehicle"]',
        '["Close_Trunk","Load_Vehicle"]',
        '["Close_Trunk"]',
    ]
    assert quality["cooccurrence_tokens"] == 2
    assert quality["singleton_actor_sequences"] == 4
    record["activities"] = [
        {"activity_id": 5, "labels": {"A": 1.0, "B": 1.0}, "intervals": [[0, 0]]}
    ]
    record["actor_sequences"] = []
    assert clip_tokens(record)[0] == ['["A","B"]']
    record["activities"] = [{"activity_id": 6, "labels": {"A": 1.0}, "intervals": [[0, 0], [2, 2]]}]
    assert clip_tokens(record)[0] == ['["A"]', '["A"]']
    record["activities"][0]["intervals"] = [[0, 0], [1, 1]]
    assert clip_tokens(record)[0] == ['["A"]']
    bank = CountBank([tokens, list(reversed(tokens))], max_n=3, min_count=1)
    case = {
        "clip": "small",
        "date": "2018-03-12",
        "tokens": ['["Close_Trunk"]', '["unseen"]'],
        "activities": 2,
        "cooccurrence_tokens": 0,
    }
    rows = score_cases([case], models(bank))
    assert len(rows) == 7
    assert all(row["predicted_tokens"] == 3 and row["oov_tokens"] == 1 for row in rows)
    assert all(math.isfinite(row["cross_entropy"]) for row in rows)
