"""
Central Logging Utilities
Provides colored terminal output and logging helpers for demo visibility.
"""

import logging
import sys


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
