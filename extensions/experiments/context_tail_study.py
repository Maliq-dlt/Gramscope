"""Fresh synthetic source-group study of conditional count tails in event streams."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict

from core.src.data import ROOT
from core.src.ngram import events
from core.src.preprocess import EOS, UNK
from extensions.experiments import event_study, registry
from extensions.experiments.event_study import conformal_p, write_csv
from extensions.experiments.event_study import score as ce_score
from extensions.src.models import CountBank, ExtensionLM

E, U, W, N, X = "E", "U", "W", "N", "X"
GROUPS = {"train": 120, "dev": 40, "calibration": 80, "test": 80}
PROTOCOL = ROOT / "extensions/results/context_tail_v1/generator_protocol.json"
MOTIF = E + U + U + W + W + U + X
HARD = E + U + W + W + U + U + X
METRICS = ("tail", "ce", "pairfrequency", "allowed_pairs")
ALPHA = 0.05
BUDGETS = (40, 80)
# Adjacent visits are legal in the longer generated streams.
CODES = {event_study.E: E, event_study.U: U, event_study.W: W, event_study.N: N, event_study.X: X}
LEGAL_PAIRS = {(CODES.get(a, a), CODES.get(b, b)) for a, b in event_study.ALLOWED} | {(X, E)}


def visit(rng, rare_rate=0.1, motif_rate=0.2, hazard_rate=0.04):
    draw = rng.random()
    if draw < hazard_rate:
        return E + U * rng.randint(1, 2) + N + X
    if draw < hazard_rate + rare_rate:
        return E + W * rng.randint(1, 2) + U * rng.randint(1, 3) + W * rng.randint(0, 1) + X
    if draw < hazard_rate + rare_rate + motif_rate:
        return MOTIF
    return E + U * rng.randint(1, 3) + W * rng.randint(1, 3) + U * rng.randint(0, 1) + X


def construct(seed):
    """Assign source IDs to partitions before drawing any symbols or labels."""
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("Seed must be a 32-bit nonnegative integer")
    ids = [f"synthetic-{seed}-{index:03}" for index in range(sum(GROUPS.values()))]
    random.Random(seed).shuffle(ids)
    split, rows, offset = {}, [], 0
    for partition, size in GROUPS.items():
        split[partition] = ids[offset : offset + size]
        offset += size
        for source in split[partition]:
            rng = random.Random(int(registry.fingerprint([seed, source])[:16], 16))
            # ponytail: shared grammar only; reviewed independent sources needed for camera claims.
            rare_rate, motif_rate = rng.uniform(0.03, 0.16), rng.uniform(0.12, 0.32)

            def background(minimum=0, maximum=3):
                return "".join(visit(rng, 0, 0, 0) for _ in range(rng.randint(minimum, maximum)))

            def add(scenario, symbols, novel=False, known_hazard=False):
                rows.append(
                    {
                        "id": f"{source}-{scenario}",
                        "source_group": source,
                        "partition": partition,
                        "scenario": scenario,
                        "symbols": symbols,
                        "latent_novel": novel,
                        "known_nohelmet_rule": known_hazard,
                    }
                )

            if partition == "train":
                for index in range(rng.randint(3, 7)):
                    add(
                        f"train-{index}",
                        "".join(
                            visit(rng, rare_rate, motif_rate, rng.uniform(0.02, 0.08))
                            for _ in range(rng.randint(1, 4))
                        ),
                    )
                continue
            add("common", background(1, 3))
            add("rare_valid", background(0, 2) + visit(rng, 1, 0, 0) + background(0, 2))
            prefix, suffix = background(0, 3), background(0, 3)
            add("paired_normal", prefix + MOTIF + suffix)
            if partition in {"dev", "test"}:
                add(
                    "known_nohelmet",
                    background(0, 2) + E + U + N + X + background(0, 2),
                    known_hazard=True,
                )
            if partition == "test":
                add("hard_replacement", prefix + HARD + suffix, novel=True)
    return rows, split


def fit(cases):
    train = [row["symbols"] for row in cases if row["partition"] == "train"]
    dev = [row["symbols"] for row in cases if row["partition"] == "dev"]
    vocabulary = sorted(set("".join(train)) | {EOS, UNK})
    bank = CountBank.from_counts(
        vocabulary,
        {n: Counter(gram for row in train for gram in events(row, n)) for n in (1, 2, 3)},
        min_count=1,
    )
    trials = []
    for method in ("witten_bell", "modified_kneser_ney"):
        for epsilon in (1e-8, 1e-4):
            model = ExtensionLM(bank, 3, method=method, epsilon=epsilon)
            dev_ce, targets = ce_score(model, dev)
            trials.append(
                {"method": method, "epsilon": epsilon, "dev_ce": dev_ce, "dev_targets": targets}
            )
    winner = min(trials, key=lambda row: (row["dev_ce"], row["method"], row["epsilon"]))
    return (
        bank,
        ExtensionLM(bank, 3, method=winner["method"], epsilon=winner["epsilon"]),
        {"winner": winner, "trials": trials},
    )


def tail_score(model, segments):
    """Max -log count-tail q; q is a score transform, never a conformal p-value."""
    bank = model.bank
    tails, coverage = [], Counter()
    for segment in segments:
        for gram in events(bank.map_sentence(segment), 3):
            context, symbol = gram[:-1], gram[-1]
            order = 3
            while order > 1 and not bank.totals[order][context[-(order - 1) :]]:
                order -= 1
            shorter = context[-(order - 1) :] if order > 1 else ()
            count = bank.totals[order][shorter]
            probability = model.score_mapped(symbol, context)
            mass = sum(
                frequency
                for candidate, frequency in bank.raw[order].items()
                if candidate[:-1] == shorter
                and model.score_mapped(candidate[-1], context) <= probability
            )
            q = (1 + mass) / (1 + count)
            tails.append(-math.log(q))
            coverage[f"order_{order}"] += 1
    return max(tails), dict(coverage)


def case_scores(model, segments):
    bank = model.bank
    tail, coverage = tail_score(model, segments)
    ce, targets = ce_score(model, segments)
    pairs = [pair for segment in segments for pair in events(bank.map_sentence(segment), 2)]
    pairfrequency = math.fsum(
        -math.log((bank.raw[2][pair] + 1) / (bank.totals[2][pair[:-1]] + len(bank.vocabulary)))
        for pair in pairs
    ) / len(pairs)
    allowed = sum(pair not in LEGAL_PAIRS for segment in segments for pair in events(segment, 2))
    return {
        "tail": tail,
        "ce": ce,
        "pairfrequency": pairfrequency,
        "allowed_pairs": allowed,
        "targets": targets,
        **{f"order_{n}": coverage.get(f"order_{n}", 0) for n in (1, 2, 3)},
    }


def calibrate(cases, model):
    by_source = defaultdict(list)
    for row in cases:
        if row["partition"] == "calibration":
            by_source[row["source_group"]].append(row)
    result = {name: [] for name in METRICS}
    for source in sorted(by_source):
        if {row["scenario"] for row in by_source[source]} != {
            "common",
            "rare_valid",
            "paired_normal",
        }:
            raise ValueError("Calibration needs exactly three normal cases per source")
        scored = [case_scores(model, [row["symbols"]]) for row in by_source[source]]
        for name in METRICS:
            result[name].append(max(row[name] for row in scored))
    if len(result["tail"]) < 60:
        raise ValueError("Insufficient normal source groups for alpha=.05")
    return result


def noise_segments(symbols, operation, rng):
    mutable = [index for index, symbol in enumerate(symbols) if symbol in (U, W)]
    if not mutable:
        raise ValueError("Noise case needs an observed helmet symbol")
    position = rng.choice(mutable)
    if operation == "drop":
        return [symbols[:position] + symbols[position + 1 :]]
    if operation == "duplicate":
        return [symbols[:position] + symbols[position] + symbols[position:]]
    if operation == "flip":
        return [symbols[:position] + (W if symbols[position] == U else U) + symbols[position + 1 :]]
    if operation == "fragment":
        middle = len(symbols) // 2
        return [symbols[:middle], symbols[middle:]]
    raise ValueError("Unknown noise operation")


def bootstrap_difference(paired_alerts, seed, samples=5000):
    rng = random.Random(seed + 4919)
    differences = []
    for _ in range(samples):
        picked = (paired_alerts[rng.randrange(len(paired_alerts))] for _ in paired_alerts)
        differences.append(math.fsum(tail - ce for tail, ce in picked) / len(paired_alerts))
    differences.sort()
    return {
        "tail_minus_ce": math.fsum(tail - ce for tail, ce in paired_alerts) / len(paired_alerts),
        "bootstrap_95_percentile": [
            differences[int(0.025 * samples)],
            differences[int(0.975 * samples) - 1],
        ],
        "resamples": samples,
        "resample_unit": "synthetic source group",
    }


def evaluate_test(cases, model, calibration, seed):
    test = [row for row in cases if row["partition"] == "test"]
    scored = [{**row, **case_scores(model, [row["symbols"]])} for row in test]
    by_source = defaultdict(dict)
    for row in scored:
        by_source[row["source_group"]][row["scenario"]] = row
    sources, paired = [], []
    for source, group in sorted(by_source.items()):
        if set(group) != {
            "common",
            "rare_valid",
            "paired_normal",
            "hard_replacement",
            "known_nohelmet",
        }:
            raise ValueError("Test source must have a matched hard replacement and a rule case")
        normal = [group[name] for name in ("common", "rare_valid", "paired_normal")]
        hard = group["hard_replacement"]
        if Counter(events(group["paired_normal"]["symbols"], 2)) != Counter(
            events(hard["symbols"], 2)
        ) or Counter(group["paired_normal"]["symbols"]) != Counter(hard["symbols"]):
            raise ValueError("Hard replacement does not preserve complete pair/unigram counts")
        if Counter(events(group["paired_normal"]["symbols"], 3)) == Counter(
            events(hard["symbols"], 3)
        ):
            raise ValueError("Hard replacement must change triples")
        alerts = {}
        for name in METRICS:
            normal_max = max(row[name] for row in normal)
            replacement_max = max(normal[0][name], normal[1][name], hard[name])
            normal_p = conformal_p(calibration[name], normal_max)
            replacement_p = conformal_p(calibration[name], replacement_max)
            sources.append(
                {
                    "source_group": source,
                    "metric": name,
                    "normal_max": normal_max,
                    "hard_replacement_max": replacement_max,
                    "normal_p": normal_p,
                    "hard_replacement_p": replacement_p,
                    "normal_alert": normal_p <= ALPHA,
                    "hard_replacement_alert": replacement_p <= ALPHA,
                }
            )
            alerts[name] = int(replacement_p <= ALPHA)
        paired.append((alerts["tail"], alerts["ce"]))
    review = []
    queue = [row for row in scored if row["scenario"] != "known_nohelmet"]
    for name in METRICS:
        ordered = sorted(
            queue,
            key=lambda row: (-row[name], registry.fingerprint([seed, row["id"], "shared-tie"])),
        )
        for budget in BUDGETS:
            picked = ordered[:budget]
            found = sum(row["latent_novel"] for row in picked)
            review.append(
                {
                    "metric": name,
                    "budget_sessions": budget,
                    "reviewed": len(picked),
                    "novel_found": found,
                    "novel_total": len(by_source),
                    "recall": found / len(by_source),
                    "precision": found / len(picked),
                    "rare_valid_reviewed": sum(row["scenario"] == "rare_valid" for row in picked),
                }
            )
    summary = {}
    for name in METRICS:
        subset = [row for row in sources if row["metric"] == name]
        summary[name] = {
            "normal_source_alerts": sum(int(row["normal_alert"]) for row in subset),
            "hard_replacement_source_alerts": sum(row["hard_replacement_alert"] for row in subset),
            "rare_valid_case_alarms": sum(
                conformal_p(calibration[name], row[name]) <= ALPHA
                for row in queue
                if row["scenario"] == "rare_valid"
            ),
            "source_groups": len(subset),
        }
    return scored, sources, review, summary, bootstrap_difference(paired, seed)


def stress_test(scored, model, calibration, seed):
    by_source = defaultdict(dict)
    for row in scored:
        by_source[row["source_group"]][row["scenario"]] = row
    output = []
    for operation in ("drop", "duplicate", "flip", "fragment"):
        for source, group in sorted(by_source.items()):
            changed = {}
            for scenario in ("common", "rare_valid", "paired_normal", "hard_replacement"):
                rng = random.Random(
                    int(registry.fingerprint([seed, source, scenario, operation])[:16], 16)
                )
                segments = noise_segments(group[scenario]["symbols"], operation, rng)
                changed[scenario] = case_scores(model, segments)
            for name in METRICS:
                normal_max = max(
                    changed[scenario][name]
                    for scenario in ("common", "rare_valid", "paired_normal")
                )
                hard_max = max(
                    changed[scenario][name]
                    for scenario in ("common", "rare_valid", "hard_replacement")
                )
                output.append(
                    {
                        "operation": operation,
                        "source_group": source,
                        "metric": name,
                        "normal_alert": conformal_p(calibration[name], normal_max) <= ALPHA,
                        "hard_replacement_alert": conformal_p(calibration[name], hard_max) <= ALPHA,
                    }
                )
    summary = {}
    for operation in ("drop", "duplicate", "flip", "fragment"):
        summary[operation] = {}
        for name in METRICS:
            subset = [
                row for row in output if (row["operation"], row["metric"]) == (operation, name)
            ]
            summary[operation][name] = {
                "normal_source_alerts": sum(int(row["normal_alert"]) for row in subset),
                "hard_replacement_source_alerts": sum(
                    int(row["hard_replacement_alert"]) for row in subset
                ),
                "source_groups": len(subset),
            }
    return output, summary


def run(seed):
    frozen_protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if seed not in frozen_protocol["seeds"] or frozen_protocol["source_groups"] != GROUPS:
        raise ValueError("Seed or source split differs from the frozen generator protocol")
    output = ROOT / "extensions/results/context_tail_v1" / f"seed{seed}"
    run_id = f"context-tail-v1-seed{seed}"
    if output.exists() or registry.run_directory(run_id).exists():
        raise FileExistsError("Experiment output or run ID already exists")
    cases, split = construct(seed)
    train = [row for row in cases if row["partition"] == "train"]
    test = [row for row in cases if row["partition"] == "test"]
    bank, model, selection = fit(cases)
    hard_pairs = Counter(gram for row in train for gram in events(row["symbols"], 2))
    if any(hard_pairs[pair] < 2 for pair in events(HARD, 2)):
        raise ValueError("Hard contrast requires supported training pairs")
    calibration = calibrate(cases, model)
    code_hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "extensions/experiments/context_tail_study.py",
            "extensions/experiments/event_study.py",
            "extensions/src/models.py",
            "core/src/ngram.py",
        )
    }
    config = {
        "experiment": "context-tail-v1",
        "seed": seed,
        "split": split,
        "case_sha256": registry.fingerprint(cases),
        "code_sha256": code_hashes,
        "generator_protocol_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "synthetic_source": "shared stochastic grammar; source groups are not cameras",
        "labels": "hard triple reorder by construction; no independent K3 truth",
        "alpha": ALPHA,
        "budgets": BUDGETS,
        "calibration": "80 source maxima of common, rare valid, matched normal; ties >=",
        "tail_q": "(1+sum_y c(h,y) I[P(y|h)<=P(x|h)])/(1+c(h)); max -log(q)",
        "tail_q_is_not_conformal_p": True,
        "missing_context": "raw-count trigram to bigram to unigram deterministic backoff",
        "known_nohelmet": "deterministic rule queue, excluded from novelty queue",
        "noise": "diagnostic shifts under unchanged clean calibration; no coverage guarantee",
    }
    directory = registry.create_run(run_id, config)
    registry.start_stage(run_id, "TAIL", config)
    registry.atomic_json(directory / "cases.json", cases)
    registry.atomic_json(directory / "selection.json", selection)
    registry.atomic_json(directory / "calibration.json", calibration)
    registry.atomic_json(
        directory / "counts.json",
        {
            "vocabulary": list(bank.vocabulary),
            "raw": {
                str(n): [[list(gram), count] for gram, count in sorted(raw.items())]
                for n, raw in bank.raw.items()
            },
        },
    )
    with (directory / "test.claim").open("x", encoding="utf-8") as stream:
        stream.write(
            registry.fingerprint(
                {"config": config, "selection": selection, "calibration": calibration}
            )
        )
    scored, sources, review, summary, difference = evaluate_test(cases, model, calibration, seed)
    stress, stress_summary = stress_test(scored, model, calibration, seed)
    output.mkdir(parents=True)
    registry.atomic_json(output / "protocol.json", config)
    registry.atomic_json(output / "cases.json", cases)
    registry.atomic_json(output / "selection.json", selection)
    registry.atomic_json(output / "calibration.json", calibration)
    write_csv(output / "scores.csv", scored)
    write_csv(output / "sources.csv", sources)
    write_csv(output / "review.csv", review)
    write_csv(output / "stress.csv", stress)
    result = {
        "source_kind": "synthetic shared grammar, no footage or independent safety labels",
        "seed": seed,
        "selected_model": selection["winner"],
        "train_sessions": len(train),
        "train_distinct_lengths": len({len(r["symbols"]) for r in train}),
        "test_sessions": len(test),
        "test_sources": GROUPS["test"],
        "hard_pair_min_training_count": min(hard_pairs[pair] for pair in events(HARD, 2)),
        "clean": summary,
        "paired_recall_difference": difference,
        "review": review,
        "noise_diagnostic": stress_summary,
        "known_nohelmet_rule_queue": {
            "test_cases": sum(row["known_nohelmet_rule"] for row in scored),
            "rule_flagged": sum(
                row["known_nohelmet_rule"] and N in row["symbols"] for row in scored
            ),
            "novelty_positive": 0,
        },
        "coverage": {
            f"order_{n}": sum(row.get(f"order_{n}", 0) for row in scored) for n in (1, 2, 3)
        },
    }
    registry.atomic_json(output / "summary.json", result)
    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.iterdir())
        if path.is_file()
    }
    registry.atomic_json(
        output / "manifest.json",
        {
            "run_id": run_id,
            "config_sha256": registry.fingerprint(config),
            "files_sha256": files,
            "test_claim_sha256": hashlib.sha256(
                (directory / "test.claim").read_bytes()
            ).hexdigest(),
        },
    )
    registry.atomic_json(
        directory / "public_manifest.json",
        {"output": str(output.relative_to(ROOT)), "files_sha256": files},
    )
    registry.complete_stage(run_id, "TAIL")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    result = run(args.seed)
    print(
        result["seed"],
        result["selected_model"],
        result["clean"],
        result["paired_recall_difference"],
    )


if __name__ == "__main__":
    main()
