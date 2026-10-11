"""Compare local modified Kneser-Ney token scores with native KenLM, without changing models."""

import argparse
import hashlib
import json
import math
import os
import random
import re
import subprocess
from pathlib import Path

from core.src.ngram import events
from core.src.preprocess import BOS, EOS, UNK
from extensions.src.models import CountBank, ExtensionLM

ROOT = Path(__file__).resolve().parents[2]
QUERY_WORD = re.compile(r"([^=\s]+)=(\d+)\s+(\d+)\s+(-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)")
ARPA_COUNT = re.compile(r"(?m)^ngram ([123])=(\d+)$")
DISCOUNTS = re.compile(r"(?m)^([123]) \d+(?:/\d+)? D1=([\d.]+) D2=([\d.]+) D3\+=([\d.]+)")


def corpus():
    # ponytail: fixed known-vocabulary fixture; add a corpus adapter for OOV/domain validation.
    rng = random.Random(1)
    letters = list("abcdefghijklm")
    return [
        rng.choices(letters, weights=range(len(letters), 0, -1), k=rng.randint(3, 7))
        for _ in range(160)
    ]


def parse_query(output, probes):
    expected = [word for sentence in probes for word in [*sentence, EOS]]
    fields = output.strip().split("\t")
    if len(fields) != len(expected):
        raise ValueError(f"KenLM returned {len(fields)} tokens, expected {len(expected)}")
    parsed = []
    for field, word in zip(fields, expected, strict=True):
        match = QUERY_WORD.fullmatch(field.strip())
        if not match or match[1] != word or match[2] == "0":
            raise ValueError(f"Invalid KenLM token or OOV: {field!r}; expected {word!r}")
        parsed.append((int(match[3]), float(match[4])))
    return parsed


def read_arpa(path):
    probabilities, backoffs = {}, {}
    section = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"\\(\d+)-grams:", line)
        if match:
            section = int(match[1])
            probabilities[section], backoffs[section] = {}, {}
            continue
        parts = line.split()
        if section and len(parts) >= section + 1 and not line.startswith("\\"):
            try:
                probability = 10 ** float(parts[0])
            except ValueError:
                continue
            gram = tuple(parts[1 : section + 1])
            probabilities[section][gram] = probability
            if len(parts) > section + 1:
                backoffs[section][gram] = 10 ** float(parts[section + 1])
    return probabilities, backoffs


def arpa_score(word, context, order, probabilities, backoffs):
    weight = 1.0
    for level in range(min(order, len(context) + 1), 0, -1):
        prefix = context[-(level - 1) :] if level > 1 else ()
        gram = prefix + (word,)
        if gram in probabilities[level]:
            return weight * probabilities[level][gram]
        if level > 1:
            weight *= backoffs[level - 1].get(prefix, 1.0)
    return 0.0


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(lmplz, query, source, output, dll_dir=None, order=3):
    for path in (lmplz, query, source / ".git"):
        if not path.exists():
            raise ValueError(f"Missing KenLM input: {path}")
    output = output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError("Output directory must stay inside this repository")
    output.mkdir(parents=True, exist_ok=False)
    sentences = corpus()
    bank = CountBank(sentences, max_n=order, min_count=1)
    local = ExtensionLM(bank, order, "modified_kneser_ney", epsilon=0)
    local_default = ExtensionLM(bank, order, "modified_kneser_ney")
    if any(d["fallback"] for d in local.mkn_discounts.values()):
        raise ValueError("Synthetic corpus unexpectedly triggers local discount fallback")
    corpus_path = output / "corpus.txt"
    corpus_path.write_bytes(("\n".join(" ".join(s) for s in sentences) + "\n").encode("utf-8"))
    arpa = output / "model.arpa"
    build_args = [
        str(lmplz.resolve()),
        "-o",
        str(order),
        "--text",
        str(corpus_path),
        "--arpa",
        str(arpa),
        "-T",
        str(output / "sort"),
        "-S",
        "256M",
        "--interpolate_unigrams",
        "0",
        "--discount_fallback",
        "0.75",
        "--verbose_header",
    ]
    environment = {**os.environ, "TEMP": str(output), "TMP": str(output)}
    if dll_dir is not None:
        environment["PATH"] = str(dll_dir.resolve()) + os.pathsep + environment["PATH"]
    build = subprocess.run(
        build_args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        check=False,
    )
    (output / "lmplz.stderr.txt").write_text(build.stderr, encoding="utf-8")
    if build.returncode:
        raise RuntimeError(f"lmplz failed ({build.returncode}): {build.stderr[-1200:]}")
    probes = [sentences[i] for i in (0, 1, 15, 80, 159)]
    probes += [sentences[2][:-1] + ["a"], ["m", "l", "k", "a"]]
    probe_bytes = ("\n".join(" ".join(s) for s in probes) + "\n").encode("utf-8")
    (output / "probes.txt").write_bytes(probe_bytes)
    query_args = [str(query.resolve()), "-v", "word", str(arpa)]
    with (output / "probes.txt").open("rb") as probe_stream:
        queried = subprocess.run(
            query_args, stdin=probe_stream, capture_output=True, env=environment, check=False
        )
    (output / "query.stdout.txt").write_bytes(queried.stdout)
    (output / "query.stderr.txt").write_bytes(queried.stderr)
    if queried.returncode:
        raise RuntimeError(f"query failed ({queried.returncode}): {queried.stderr[-1200:]!r}")
    external = parse_query(queried.stdout.decode("utf-8"), probes)
    source_diff = subprocess.check_output(
        ["git", "-C", str(source.resolve()), "diff", "--binary"],
        text=True,
        encoding="utf-8",
    )
    source_status = subprocess.check_output(
        ["git", "-C", str(source.resolve()), "status", "--short"],
        text=True,
        encoding="utf-8",
    )
    source_sha = subprocess.check_output(
        ["git", "-C", str(source.resolve()), "rev-parse", "HEAD"], text=True, encoding="utf-8"
    ).strip()
    kenlm_fallback_orders = [
        int(level)
        for level in re.findall(r"Substituting fallback discounts for order (\d+)", build.stderr)
    ]
    discounts = {
        int(order): tuple(float(value) for value in values)
        for order, *values in DISCOUNTS.findall(build.stderr)
    }
    kenlm_counts = dict(ARPA_COUNT.findall(arpa.read_text(encoding="utf-8")))
    probabilities, backoffs = read_arpa(arpa)
    external_discount = discounts[order]
    masses = {}
    for gram, count in bank.raw[order].items():
        prefix = gram[:-1]
        masses[prefix] = masses.get(prefix, 0.0) + external_discount[min(count, 3) - 1]
    rows = []
    formula_residuals = []
    finite = []
    local_logs = []
    external_logs = []
    epsilon_deltas = []
    backed_off = 0
    unseen_trigrams = 0
    offset = 0
    for sentence_index, sentence in enumerate(probes):
        for gram in events(sentence, order):
            context, word = gram[:-1], gram[-1]
            matched_order, external_log10 = external[offset]
            offset += 1
            local_probability = local.score_mapped(word, context)
            local_log10 = math.log10(local_probability) if local_probability else None
            default_log10 = math.log10(local_default.score_mapped(word, context))
            if local_log10 is not None:
                epsilon_deltas.append(abs(default_log10 - local_log10))
            count = bank.raw[order][context + (word,)]
            total = bank.totals[order][context]
            if count and matched_order == order:
                lower = arpa_score(word, context[1:], order - 1, probabilities, backoffs)
                direct = max(count - external_discount[min(count, 3) - 1], 0) / total
                reconstructed = direct + masses[context] / total * lower
                formula_residuals.append(abs(math.log10(reconstructed) - external_log10))
            external_logs.append(external_log10)
            if local_log10 is not None:
                local_logs.append(local_log10)
                finite.append(abs(local_log10 - external_log10))
            backed_off += matched_order < order
            unseen_trigrams += bank.raw[order][context + (word,)] == 0
            rows.append(
                {
                    "sentence": sentence_index,
                    "context": list(context),
                    "word": word,
                    "local_count_highest_order": bank.raw[order][context + (word,)],
                    "local_context_total_highest_order": bank.totals[order][context],
                    "kenlm_matched_order": matched_order,
                    "local_log10": local_log10,
                    "kenlm_log10": external_log10,
                    "delta_log10_local_minus_kenlm": (
                        local_log10 - external_log10 if local_log10 is not None else None
                    ),
                }
            )
    contexts = [(BOS,) * (order - 1), ("a",) * (order - 1), ("m", "l")[-(order - 1) :]]
    kenlm_words = [gram[0] for gram in probabilities[1] if gram[0] != BOS]
    normalization = [
        {
            "context": list(context),
            "local_sum": math.fsum(local.score_mapped(word, context) for word in bank.vocabulary),
            "kenlm_arpa_sum": math.fsum(
                arpa_score(word, context, order, probabilities, backoffs) for word in kenlm_words
            ),
        }
        for context in contexts
    ]
    receipt = {
        "claim": "External MKN token-score comparison; policies prevent exact equivalence",
        "order": order,
        "ngram_types": {
            str(level): {
                "local_raw": len(bank.raw[level]),
                "kenlm_arpa": int(kenlm_counts[str(level)]) if str(level) in kenlm_counts else None,
            }
            for level in range(1, order + 1)
        },
        "source": {
            "url": "https://github.com/kpu/kenlm",
            "sha": source_sha,
            "local_source_diff": source_diff,
            "local_source_status": source_status,
            "lmplz_sha256": sha256(lmplz),
            "query_sha256": sha256(query),
            "adapter_sha256": sha256(Path(__file__)),
        },
        "corpus": {
            "sha256": sha256(corpus_path),
            "bytes": corpus_path.stat().st_size,
            "sentences": len(sentences),
            "word_tokens": sum(map(len, sentences)),
            "vocabulary": sorted(bank.vocab_set),
            "min_count": 1,
        },
        "probes": {
            "sha256": hashlib.sha256(probe_bytes).hexdigest(),
            "sentences": len(probes),
            "predicted_tokens": len(rows),
        },
        "commands": {"lmplz": build_args, "query": query_args},
        "normalization": normalization,
        "unigram_unk_mass": {
            "local": local.score_mapped(UNK, ()),
            "kenlm_arpa": probabilities[1][("<unk>",)],
            "local_default_epsilon_1e_8": local_default.score_mapped(UNK, ()),
        },
        "formula_check": {
            "direct_matched_tokens": len(formula_residuals),
            "max_abs_residual_log10": max(formula_residuals) if formula_residuals else None,
            "mean_abs_residual_log10": (
                math.fsum(formula_residuals) / len(formula_residuals) if formula_residuals else None
            ),
            "compatible_at_1e_4_log10": bool(formula_residuals) and max(formula_residuals) < 1e-4,
            "method": "Local top-order counts and context mass with KenLM printed "
            "discounts and ARPA lower-order probabilities",
        },
        "kenlm_fallback_orders_zero_based": kenlm_fallback_orders,
        "discounts": {
            str(order): {
                "local": list(info["discounts"]),
                "kenlm_stderr": list(discounts[order]) if order in discounts else None,
                "local_fallback": info["fallback"],
            }
            for order, info in local.mkn_discounts.items()
        },
        "policy_differences": [
            "KenLM reserves <unk> and allocates probability to it; "
            "local <UNK> has zero mass with epsilon=0.",
            "KenLM unigram ARPA includes reserved <s> and <unk>; local event unigrams omit both.",
            "KenLM --interpolate_unigrams 0 assigns lower-order residual mass to <unk>; "
            "the local unigram uses continuation frequency without residual interpolation.",
            "KenLM allows zero/endpoint estimated discounts; local requires 0 < D_i < i "
            "and otherwise falls back to (0.75, 0.75, 0.75).",
            "KenLM stores rounded log10 ARPA scores; local scores are Python float probabilities.",
            "Historical ExtensionLM defaults epsilon=1e-8; this comparison uses epsilon=0 "
            "and reports the known-token delta separately.",
            "KenLM suppresses repeated-BOS higher-order grams; local events uses "
            "n-1 BOS prefixes, affecting trigram count-of-counts and lower-order discounts.",
            "Both inputs are whitespace-tokenized, one sentence per line, with implicit BOS/EOS; "
            "all training and probe words are known, so no UNK mapping is compared.",
            "Probes mix training and perturbed in-vocabulary sentences; this checks arithmetic, "
            "not held-out generalization.",
        ],
        "summary": {
            "tokens": len(rows),
            "finite_local_tokens": len(finite),
            "max_abs_delta_log10": max(finite) if finite else None,
            "mean_abs_delta_log10": math.fsum(finite) / len(finite) if finite else None,
            "kenlm_backed_off_tokens": backed_off,
            "local_unseen_highest_order": unseen_trigrams,
            "max_abs_delta_log10_default_vs_zero_epsilon": max(epsilon_deltas),
            "local_probe_cross_entropy_nats": (
                -math.log(10) * math.fsum(local_logs) / len(rows)
                if len(local_logs) == len(rows)
                else None
            ),
            "kenlm_probe_cross_entropy_nats": -math.log(10) * math.fsum(external_logs) / len(rows),
        },
        "rows": rows,
    }
    (output / "comparison.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return receipt["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lmplz", type=Path, required=True)
    parser.add_argument("--query", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dll-dir", type=Path)
    parser.add_argument("--order", type=int, choices=(2, 3), default=3)
    parser.add_argument("--output", type=Path, default=ROOT / ".tmp/academic_upgrade_v2/validation")
    args = parser.parse_args()
    print(
        json.dumps(run(args.lmplz, args.query, args.source, args.output, args.dll_dir, args.order))
    )


if __name__ == "__main__":
    main()
