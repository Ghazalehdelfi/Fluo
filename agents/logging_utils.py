"""
Central Logging Utilities
Provides colored terminal output and logging helpers for demo visibility.
"""

import json
import logging
import re
import sys

_retry_logger = logging.getLogger(__name__)


# ANSI color codes for terminal output
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"
    MAGENTA = "\033[35m"


def setup_logging():
    """Configure root logger for comprehensive demo output."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)


def log_section(logger: logging.Logger, title: str):
    """Log a visually distinct section header."""
    border = "═" * 60
    logger.info(f"\n{Colors.CYAN}{border}{Colors.END}")
    logger.info(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.END}")
    logger.info(f"{Colors.CYAN}{border}{Colors.END}")


def log_api_call(logger: logging.Logger, method: str, endpoint: str, details: str = ""):
    """Log API calls with visual formatting."""
    border = "─" * 60
    logger.info(f"\n{Colors.BLUE}{border}{Colors.END}")
    logger.info(f"{Colors.BOLD}{Colors.BLUE}📡 API {method}: {endpoint}{Colors.END}")
    if details:
        logger.info(f"   {details}")
    logger.info(f"{Colors.BLUE}{border}{Colors.END}")


def log_step(logger: logging.Logger, step_num: int, description: str):
    """Log a numbered step."""
    logger.info(f"   {Colors.YELLOW}Step {step_num}:{Colors.END} {description}")


def log_success(logger: logging.Logger, message: str):
    """Log a success message."""
    logger.info(f"   {Colors.GREEN}✓ {message}{Colors.END}")


def log_warning(logger: logging.Logger, message: str):
    """Log a warning message."""
    logger.info(f"   {Colors.YELLOW}⚠ {message}{Colors.END}")


def log_error(logger: logging.Logger, message: str):
    """Log an error message."""
    logger.error(f"   {Colors.RED}✗ {message}{Colors.END}")


def log_info(logger: logging.Logger, message: str, indent: int = 0):
    """Log an info message with optional indentation."""
    prefix = "   " * indent
    logger.info(f"{prefix}{message}")


def parse_json_response(message) -> dict:
    """
    Safely extract and parse JSON from an OpenAI chat completion message.

    Handles:
    - None / empty content (e.g. model refusal stored in message.refusal)
    - Markdown code fences: ```json ... ``` or ``` ... ```
    - Leading/trailing whitespace
    """
    content = getattr(message, "content", None)

    if not content:
        refusal = getattr(message, "refusal", None)
        raise ValueError(f"Model returned no content. Refusal: {refusal!r}")

    # Strip markdown code fences that some models add
    stripped = content.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped).strip()

    return json.loads(stripped)


def call_llm_with_json(
    create_fn,
    *,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    model: str = None,
    **kwargs,
) -> dict:
    """
    Call ``create_fn(**kwargs)`` (an OpenAI chat.completions.create bound method),
    parse the JSON response, and automatically retry up to *max_retries* times
    when the model returns empty or refused content.

    Cost tracking is handled automatically by the TrackedOpenAI client wrapper;
    no separate cost_tracker is needed here.

    Args:
        create_fn:    Bound method – e.g. ``client.chat.completions.create``.
        max_retries:  Maximum number of attempts (default 3).
        retry_delay:  Base delay in seconds between retries (doubles each attempt).
        model:        Model name string forwarded to the API call.
        **kwargs:     Forwarded verbatim to *create_fn* (model, messages, …).

    Returns:
        Parsed JSON dict from the model response.

    Raises:
        ValueError: If all retries are exhausted without a valid response.
    """
    import time

    call_kwargs = kwargs if model is None else {"model": model, **kwargs}

    last_error: Exception = None
    for attempt in range(max_retries):
        if attempt > 0:
            time.sleep(retry_delay * (2 ** (attempt - 1)))
        response = create_fn(**call_kwargs)
        try:
            return parse_json_response(response.choices[0].message)
        except (ValueError, json.JSONDecodeError) as exc:
            # ValueError: empty/refused content. JSONDecodeError: truncated or
            # malformed JSON (e.g. hit max_completion_tokens mid-string).
            finish = getattr(response.choices[0], "finish_reason", None)
            _retry_logger.warning(
                "LLM JSON parse failed (attempt %d/%d, finish_reason=%s): %s",
                attempt + 1,
                max_retries,
                finish,
                exc,
            )
            last_error = exc
    raise last_error


def log_key_value(logger: logging.Logger, key: str, value: str, indent: int = 1):
    """Log a key-value pair."""
    prefix = "   " * indent
    logger.info(f"{prefix}{Colors.YELLOW}{key}:{Colors.END} {value}")


def log_list_item(logger: logging.Logger, item: str, indent: int = 2):
    """Log a list item with bullet point."""
    prefix = "   " * indent
    logger.info(f"{prefix}• {item}")


def print_startup_banner():
    """Print the application startup banner."""
    print(f"\n{Colors.CYAN}{'═' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  🌍 Fluo - Backend Server{Colors.END}")
    print(f"{Colors.CYAN}{'═' * 60}{Colors.END}")
    print(f"  {Colors.GREEN}✓{Colors.END} Comprehensive logging enabled for demo")
    print(f"{Colors.CYAN}{'═' * 60}{Colors.END}\n")
