"""Docker entry point — starts the autonomous 24-hour loop."""

import asyncio

from dotenv import load_dotenv

load_dotenv()

from src.scheduler import run_loop  # noqa: E402

if __name__ == "__main__":
    asyncio.run(run_loop())
