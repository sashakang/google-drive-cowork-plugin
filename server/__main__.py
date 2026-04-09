"""Allow running as `python3 -m server`."""
from .main import main
import asyncio

asyncio.run(main())
