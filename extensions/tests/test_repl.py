"""One IO regression reuses actual checkpoint/scoring logic."""

import io

from extensions.src.cli import save_model
from extensions.src.models import CountBank, ExtensionLM
from extensions.src.repl import repl


def test_repl_preserves_model_after_bad_path_and_eof(tmp_path):
    model = ExtensionLM(
        CountBank([["the", "cat"], ["the", "dog"]], max_n=2, min_count=1), 2, "witten_bell"
    )
    path = tmp_path / "model.json.gz"
    save_model(path, model, {})
    before = path.read_bytes()
    output = io.StringIO()
    assert (
        repl(
            path,
            io.StringIO("/topk the\n/model missing.json.gz\n/score the cat\n/info\n/quit\n"),
            output,
        )
        == 0
    )
    assert (
        "probability" in output.getvalue()
        and "perplexity" in output.getvalue()
        and "Error:" in output.getvalue()
    )
    assert path.read_bytes() == before
    assert repl(path, io.StringIO(), io.StringIO()) == 0
