"""Run the development relay on a free port; print the port."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dev_relay import DevRelay  # noqa: E402


async def main():
    server, port = await DevRelay().serve()
    print(port, flush=True)
    await server.wait_closed()

asyncio.run(main())
