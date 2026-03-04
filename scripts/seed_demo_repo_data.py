from __future__ import annotations

import json


def main() -> None:
    payload = {
        "demo_repo": "demo/hooked-demo",
        "pull_requests": [
            {"number": 42, "title": "Add payment retries", "status": "open"},
            {"number": 43, "title": "Tighten auth middleware", "status": "merged"},
        ],
        "notes": [
            "Use these values to script Loom screenshots.",
            "Hooked itself does not write back to GitHub in v1.",
        ],
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
