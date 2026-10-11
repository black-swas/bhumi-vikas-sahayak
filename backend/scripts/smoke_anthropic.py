"""One live Haiku 5.5 call: prints model ID, usage and stop_reason.

Haiku 5.5 request rules: no temperature/top_p/top_k, no assistant prefill, no budget_tokens.
Thinking is on by default and counts toward max_tokens, so blocks are read by type.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from _env import load_env  # noqa: E402

load_env()


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set (put it in .env). Skipping live call.")
        return 1

    import anthropic

    model = os.environ.get("ANTHROPIC_MODEL_ANSWER", "claude-haiku-5-5")
    effort = os.environ.get("ANTHROPIC_EFFORT", "low")
    client = anthropic.Anthropic(
        timeout=float(os.environ.get("ANTHROPIC_TIMEOUT_S", "15")), max_retries=1
    )

    t0 = time.perf_counter()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1500,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        )
    except anthropic.APIStatusError as e:
        print(f"API error {e.status_code}: {type(e).__name__} (request id: {e.request_id})")
        return 1
    except anthropic.APIConnectionError as e:
        print(f"connection error: {type(e).__name__}")
        return 1
    wall = time.perf_counter() - t0

    print("model:", resp.model)
    print("stop_reason:", resp.stop_reason)
    print("block types:", [b.type for b in resp.content])
    print("reply:", "".join(b.text for b in resp.content if b.type == "text"))
    print("usage:", resp.usage)
    print(f"wall clock: {wall:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
