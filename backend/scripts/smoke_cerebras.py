"""One live Cerebras call: prints model IDs, time_info, usage and cached tokens."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from _env import load_env  # noqa: E402

load_env()


def main() -> int:
    if not os.environ.get("CEREBRAS_API_KEY"):
        print("CEREBRAS_API_KEY is not set (put it in .env). Skipping live call.")
        return 1

    from cerebras.cloud.sdk import Cerebras

    model = os.environ.get("CEREBRAS_MODEL_UNDERSTAND", "qwen-3.8-27b")
    client = Cerebras(timeout=float(os.environ.get("CEREBRAS_TIMEOUT_S", "15")), max_retries=1)

    try:
        listed = [m.id for m in client.models.list().data]
        print("available models:", ", ".join(sorted(listed)))
        if model not in listed:
            print(f"WARNING: {model} is not in the model list")
    except Exception as e:  # smoke script: report any failure class
        print(f"models.list failed: {type(e).__name__}")

    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        max_completion_tokens=50,
    )
    wall = time.perf_counter() - t0

    print("model:", resp.model)
    print("reply:", resp.choices[0].message.content)
    print("finish_reason:", resp.choices[0].finish_reason)
    print("time_info:", getattr(resp, "time_info", None))
    usage = resp.usage
    print("usage:", usage)
    details = getattr(usage, "prompt_tokens_details", None)
    print("cached_tokens:", getattr(details, "cached_tokens", None))
    print(f"wall clock: {wall:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
