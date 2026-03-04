from __future__ import annotations

import asyncio

from app.bootstrap import build_container, start_container, stop_container


async def main() -> None:
    container = build_container()
    await start_container(container)
    try:
        await container.overdue_scanner.run()
        print("Overdue nudge scan completed.")
    finally:
        await stop_container(container)


if __name__ == "__main__":
    asyncio.run(main())
