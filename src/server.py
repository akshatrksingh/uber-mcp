import logging
import sys

import click
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src import provider as _prov
from src.mock_provider import MockProvider
from src.tools.geocode import uber_geocode
from src.tools.ride_options import uber_get_ride_options
from src.tools.request_ride import uber_request_ride
from src.tools.ride_status import uber_get_ride_status
from src.tools.cancel_ride import uber_cancel_ride
from src.tools.auth import uber_authenticate

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

mcp = FastMCP('uber-mcp')

# Register all tools
mcp.tool()(uber_authenticate)
mcp.tool()(uber_geocode)
mcp.tool()(uber_get_ride_options)
mcp.tool()(uber_request_ride)
mcp.tool()(uber_get_ride_status)
mcp.tool()(uber_cancel_ride)


def _configure_provider(mock: bool) -> None:
    """Set the active provider based on the --mock flag.

    Args:
        mock: If True, use MockProvider. Real provider added in Phase 4.
    """
    if mock:
        _prov.configure(MockProvider())
    else:
        # Phase 4: wire real UberClient here
        _prov.configure(MockProvider())
        logger.warning('Real Uber client not yet implemented — falling back to mock')


@click.command()
@click.option('--mock', is_flag=True, default=False, help='Use mock provider instead of real Uber API.')
def main(mock: bool) -> None:
    """Start the Uber MCP server over stdio."""
    _configure_provider(mock=mock)
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
