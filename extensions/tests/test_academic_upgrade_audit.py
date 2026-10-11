"""Development-only reproduction checks on actual count banks."""

import pytest

from extensions.experiments.academic_upgrade import group_se, select_one_se
from extensions.experiments.academic_upgrade_audit import check_selection
from extensions.src.analytics import aggregate, document_losses
from extensions.src.models import CountBank, ExtensionLM


def test_reproduced_one_se_rejects_a_changed_receipt():
    train = [
        ["the", "worker", "wears", "helmet"],
        ["the", "worker", "wears", "gloves"],
        ["the", "driver", "wears", "helmet"],
    ]
    dev = [
        {"id": f"document-{i}", "split_group": f"group-{i}", "sentences": [sentence]}
        for i, sentence in enumerate(
            (
                ["the", "worker", "wears", "helmet"],
                ["the", "driver", "wears", "gloves"],
                ["worker", "wears", "helmet"],
            )
        )
    ]
    bank = CountBank(train, max_n=2, min_count=2)
    losses = {}
    rows = []
    for n in (1, 2):
        name = f"{n}-kneser_ney"
        losses[name] = document_losses(ExtensionLM(bank, n, "kneser_ney"), dev)
        rows.append(
            {
                "model": name,
                "n": n,
                "method": "kneser_ney",
                "dev_ce_nats": aggregate(losses[name])["cross_entropy"],
            }
        )
    best = min(rows, key=lambda row: (row["dev_ce_nats"], row["model"]))
    recorded = select_one_se(rows, group_se(losses[best["model"]]))
    assert check_selection(rows, losses, recorded)[1] == {"best_se_nats": 0, "ceiling_nats": 0}
    with pytest.raises(ValueError, match="statistic differs"):
        check_selection(rows, losses, dict(recorded, best_se_nats=recorded["best_se_nats"] + 0.01))
    with pytest.raises(ValueError, match="selection differs"):
        check_selection(rows, losses, dict(recorded, one_se="missing-model"))
