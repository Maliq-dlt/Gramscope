"""Small contract checks for the KenLM comparison adapter."""

import pytest

from extensions.experiments.kenlm_validation import arpa_score, corpus, parse_query, read_arpa
from extensions.src.models import CountBank, ExtensionLM


def test_corpus_has_estimable_discounts_without_unknown_training_words():
    sentences = corpus()
    bank = CountBank(sentences, max_n=3, min_count=1)
    model = ExtensionLM(bank, 3, "modified_kneser_ney", epsilon=0)
    assert len(sentences) == 160
    assert all(word in bank.vocab_set for sentence in sentences for word in sentence)
    assert all(info["fallback"] is None for info in model.mkn_discounts.values())


def test_query_parser_checks_token_alignment_and_oov():
    probes = [["a", "b"], ["c"]]
    output = "a=1 2 -0.2\tb=2 3 -0.3\t</s>=3 3 -0.4\tc=4 2 -0.5\t</s>=3 3 -0.6\t"
    assert parse_query(output, probes) == [(2, -0.2), (3, -0.3), (3, -0.4), (2, -0.5), (3, -0.6)]
    with pytest.raises(ValueError, match="Invalid KenLM token or OOV"):
        parse_query(output.replace("c=4", "c=0"), probes)
    with pytest.raises(ValueError, match="returned"):
        parse_query(output.rsplit("c=4", 1)[0], probes)


def test_arpa_backoff_reconstructs_normalized_context(tmp_path):
    arpa = tmp_path / "tiny.arpa"
    arpa.write_text(
        "\\1-grams:\n-0.30103 a -0.22184875\n-0.30103 b\n\\2-grams:\n-0.15490196 a a\n\\end\\\n",
        encoding="utf-8",
    )
    probabilities, backoffs = read_arpa(arpa)
    assert arpa_score("a", ("a",), 2, probabilities, backoffs) == pytest.approx(0.7)
    assert arpa_score("b", ("a",), 2, probabilities, backoffs) == pytest.approx(0.3)
