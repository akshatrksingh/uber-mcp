"""CLI agent — chat with Claude to book Uber rides via the MCP server."""
import asyncio
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import click
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(Path(__file__).parent.parent / '.env')

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TRANSCRIPTS_DIR = PROJECT_ROOT / 'transcripts'
_CHROME_PROFILE = Path.home() / '.uber-mcp' / 'chrome-profile'

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

# Matches log lines: timestamp prefix OR level keywords anywhere on the line.
_LOG_LINE_RE = re.compile(
    r'^\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}'  # timestamp prefix
    r'|^\[?\d{2}:\d{2}:\d{2}'                       # short timestamp
    r'|\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b',
    re.IGNORECASE,
)


def _strip_log_lines(text: str) -> str:
    """Remove log lines from a block of text."""
    lines = [l for l in text.splitlines() if not _LOG_LINE_RE.search(l)]
    return '\n'.join(lines).strip()


def _transcript_filename(first_message: str, now: datetime) -> str:
    """Build a transcript filename from the timestamp and first user message.

    Example: 2026-03-27_2315_book_uber_nyu.md
    """
    words = re.sub(r'[^\w\s]', '', first_message.lower()).split()
    slug = '_'.join(words[:5])  # up to 5 words
    return f'{now.strftime("%Y-%m-%d_%H%M")}_{slug}.md'


def _write_transcript(
    turns: list[tuple[str, str]],
    first_message: str,
    mode: str,
    now: datetime,
) -> Path:
    """Write a clean markdown transcript to transcripts/.

    Args:
        turns: List of (user_text, agent_text) pairs.
        first_message: The first user message (used in heading and filename).
        mode: 'live' or 'mock'.
        now: Session start datetime.

    Returns:
        Path of the written file.
    """
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    filename = _transcript_filename(first_message, now)
    path = TRANSCRIPTS_DIR / filename

    lines = [
        f'# Transcript: {first_message}',
        f'**Mode:** {mode}',
        f'**Date:** {now.strftime("%Y-%m-%d %H:%M")}',
        '---',
        '',
    ]
    for user_text, agent_text in turns:
        lines.append(f'**User:** {user_text}')
        lines.append('')
        if agent_text:
            lines.append(f'**Agent:** {_strip_log_lines(agent_text)}')
            lines.append('')

    path.write_text('\n'.join(lines))
    return path


def _to_anthropic_tools(mcp_tools) -> list[dict]:
    """Convert MCP tool list to Anthropic tool dicts."""
    return [
        {
            'name': t.name,
            'description': t.description or '',
            'input_schema': t.inputSchema,
        }
        for t in mcp_tools
    ]


def _extract_text(content_blocks) -> str:
    """Pull text from a list of content blocks."""
    return ''.join(b.text for b in content_blocks if hasattr(b, 'text'))


async def _agent_loop(mock: bool) -> None:
    """Connect to the MCP server and run the conversational REPL."""
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
            turns: list[tuple[str, str]] = []   # (user_text, agent_text)
            session_start = datetime.now()
            mode_label = 'mock' if mock else 'live'

            print(f'Uber Agent [{mode_label}] — type "exit" to quit.\n')

            try:
                while True:
                    try:
                        user_input = input('You: ').strip()
                    except EOFError:
                        break

                    if not user_input:
                        continue
                    if user_input.lower() in ('exit', 'quit', 'q'):
                        break

                    messages.append({'role': 'user', 'content': user_input})
                    agent_reply = ''

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
                                agent_reply = text
                            messages.append({'role': 'assistant', 'content': response.content})
                            break

                    turns.append((user_input, agent_reply))

            except KeyboardInterrupt:
                pass
            finally:
                print('\nGoodbye!')
                if turns:
                    first_msg = turns[0][0]
                    path = _write_transcript(turns, first_msg, mode_label, session_start)
                    print(f'Transcript saved: {path.relative_to(PROJECT_ROOT)}')


def _ensure_browser_setup(mock: bool) -> None:
    """Run first-time browser auth setup if the Chrome profile doesn't exist yet."""
    if mock or _CHROME_PROFILE.exists():
        return
    print('First-time setup: no saved Uber session found.')
    print('A browser will open — please log in to your Uber account.')
    print()
    import subprocess
    result = subprocess.run(
        ['uv', 'run', 'python', 'setup_browser.py'],
        cwd=str(PROJECT_ROOT),
    )
    if result.returncode != 0:
        print('Browser setup failed. Run `uv run python setup_browser.py` manually.', file=sys.stderr)
        sys.exit(1)
    print()


@click.command()
@click.option('--mock', is_flag=True, default=False, help='Use mock provider (no Uber credentials needed).')
def main(mock: bool) -> None:
    """Chat with Claude to book Uber rides."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    _ensure_browser_setup(mock=mock)
    asyncio.run(_agent_loop(mock=mock))


if __name__ == '__main__':
    main()
