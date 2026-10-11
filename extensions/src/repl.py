"""Read-only academic REPL; checkpoints and historical sampler remain unchanged."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from core.src.preprocess import preprocess, tokenize
from extensions.src.analytics import top_k
from extensions.src.cli import load_model, model_info, score_sentence


def repl(path, input_stream=None, output=None):
    input_stream = sys.stdin if input_stream is None else input_stream
    output = sys.stdout if output is None else output
    model, _ = load_model(path)
    print(
        "N-gram REPL: /model <checkpoint>, /topk <context>, /score <text>, /info, /quit",
        file=output,
    )
    while True:
        try:
            print("> ", end="", file=output, flush=True)
            line = input_stream.readline(65538)
            if not line:
                return 0
            if len(line.encode("utf-8")) > 65536 or "\x00" in line:
                raise ValueError("Input must be <=64 KiB UTF-8 without NUL")
            command, _, argument = line.strip().partition(" ")
            if command == "/quit":
                return 0
            if command == "/model":
                candidate = Path(argument)
                next_model, _ = load_model(candidate)
                model, path = next_model, candidate
                print("Model: " + str(path), file=output)
            elif command == "/info":
                print(json.dumps(model_info(path), ensure_ascii=False), file=output)
            elif command == "/score":
                print(json.dumps(score_sentence(model, argument), ensure_ascii=False), file=output)
            elif command == "/topk":
                sentences, _ = preprocess([tokenize(argument)])
                context = sentences[0] if sentences else []
                if len(context) > 4096:
                    raise ValueError("Context must be <=4096 words")
                print(json.dumps(top_k(model, context), ensure_ascii=False), file=output)
            else:
                print(
                    "Use /model, /topk, /score, /info or /quit. "
                    "CCTV symbols use the event runner instead of word tokenization.",
                    file=output,
                )
        except (ValueError, TypeError, KeyError, OSError, EOFError) as error:
            print("Error: " + str(error), file=output)
        except KeyboardInterrupt:
            print("", file=output)
            return 0
