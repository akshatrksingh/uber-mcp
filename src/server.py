import logging
import sys

import click
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from src import provider as _prov
from src.browser_provider import BrowserProvider
from src.mock_provider import MockProvider
from src.tools.geocode import uber_geocode
from src.tools.ride_options import uber_get_ride_options
from src.tools.request_ride import uber_request_ride
from src.tools.ride_status import uber_get_ride_status
from src.tools.cancel_ride import uber_cancel_ride
from src.tools.auth import uber_authenticate
from src.tools.ride_history import uber_ride_history

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
mcp.tool()(uber_ride_history)


def _configure_provider(mock: bool) -> None:
    """Set the active provider based on the --mock flag.

    Args:
        mock: If True, use MockProvider. Otherwise use UberClient with AuthManager.
    """
    if mock:
        _prov.configure(MockProvider())
    else:
        _prov.configure(BrowserProvider())


@click.command()
@click.option('--mock', is_flag=True, default=False, help='Use mock provider instead of real Uber API.')
def main(mock: bool) -> None:
    """Start the Uber MCP server over stdio."""
    _configure_provider(mock=mock)
    mcp.run(transport='stdio')


if __name__ == '__main__':
    main()
