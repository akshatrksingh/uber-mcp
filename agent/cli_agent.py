"""CLI agent — chat with Claude to book Uber rides via the MCP server."""
import asyncio
import json
import logging
import sys
from pathlib import Path

import anthropic
import click
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(Path(__file__).parent.parent / '.env')

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent

# Spec says claude-sonnet-4-20250514; using claude-sonnet-4-5 (closest stable ID).
# Deviation logged in SYSTEM_DESIGN.md Changelog.
MODEL = 'claude-sonnet-4-5'

SYSTEM_PROMPT = """You are an Uber ride-booking assistant. Help users find and book rides using the available tools.

WORKFLOW — follow this exact order for every ride request:
1. Call uber_geocode for the pickup location.
2. Call uber_geocode for the destination.
3. Call uber_get_ride_options with both coordinate pairs.
4. Present the options clearly: name, price range (low–high), ETA, capacity.
5. Ask the user which option they want.
6. Call uber_request_ride with confirm=false to show the exact upfront fare.
7. Present the fare and ETA, then ask: "Shall I book this ride? (yes/no)"
8. Only call uber_request_ride with confirm=true after the user says yes.

RULES:
- Never book (confirm=true) without explicit user confirmation.
- Never skip the preview step — confirm=false must always come before confirm=true.
- If uber_geocode returns ambiguous results, list the options and ask the user to pick one.
- Translate tool errors into plain language; suggest the next step.
- After a confirmed booking share the driver name, vehicle details, and ETA.
- Keep replies concise. Use bullet points for ride options."""


def _to_anthropic_tools(mcp_tools) -> list[dict]:
    """Convert MCP tool list to Anthropic tool dicts.

    Args:
        mcp_tools: List of MCP Tool objects from session.list_tools().

    Returns:
        List of dicts in Anthropic tool format.
    """
    return [
        {
            'name': t.name,
            'description': t.description or '',
            'input_schema': t.inputSchema,
        }
        for t in mcp_tools
    ]


def _extract_text(content_blocks) -> str:
    """Pull text from a list of content blocks.

    Args:
        content_blocks: List of Anthropic content block objects.

    Returns:
        Concatenated text from all TextBlock entries.
    """
    return ''.join(b.text for b in content_blocks if hasattr(b, 'text'))


async def _agent_loop(mock: bool) -> None:
    """Connect to the MCP server and run the conversational REPL.

    Args:
        mock: If True, passes --mock to the MCP server subprocess.
    """
    server_params = StdioServerParameters(
        command='uv',
        args=['run', 'python', '-m', 'src.server'] + (['--mock'] if mock else []),
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = _to_anthropic_tools(tools_result.tools)
            logger.info('Connected to MCP server — %d tools available', len(tools))

            client = anthropic.Anthropic()
            messages: list[dict] = []

            mode_label = 'mock' if mock else 'live'
            print(f'Uber Agent [{mode_label}] — type "exit" to quit.\n')

            while True:
                try:
                    user_input = input('You: ').strip()
                except (EOFError, KeyboardInterrupt):
                    print('\nGoodbye!')
                    break

                if not user_input:
                    continue
                if user_input.lower() in ('exit', 'quit', 'q'):
                    print('Goodbye!')
                    break

                messages.append({'role': 'user', 'content': user_input})

                # Agentic loop: run until Claude stops calling tools.
                while True:
                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=tools,  # type: ignore[arg-type]
                        messages=messages,
                    )

                    if response.stop_reason == 'tool_use':
                        tool_results = []
                        for block in response.content:
                            if block.type != 'tool_use':
                                continue
                            logger.info('Tool call: %s args=%s', block.name, block.input)
                            print(f'  [{block.name}]', flush=True)
                            result = await session.call_tool(block.name, block.input)
                            raw = (
                                result.content[0].text
                                if result.content
                                else json.dumps({'error': 'EMPTY_RESPONSE'})
                            )
                            tool_results.append({
                                'type': 'tool_result',
                                'tool_use_id': block.id,
                                'content': raw,
                            })

                        messages.append({'role': 'assistant', 'content': response.content})
                        messages.append({'role': 'user', 'content': tool_results})

                    else:
                        text = _extract_text(response.content)
                        if text:
                            print(f'\nAgent: {text}\n')
                        messages.append({'role': 'assistant', 'content': response.content})
                        break


@click.command()
@click.option('--mock', is_flag=True, default=False, help='Use mock provider (no Uber credentials needed).')
def main(mock: bool) -> None:
    """Chat with Claude to book Uber rides."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    asyncio.run(_agent_loop(mock=mock))


if __name__ == '__main__':
    main()
