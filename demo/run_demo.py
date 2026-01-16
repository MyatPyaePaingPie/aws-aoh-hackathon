#!/usr/bin/env python3
"""
HoneyAgent Live Demo Runner

Runs the attack sequence automatically with visual output.
Perfect for presentations - just start and watch.

Usage:
    python demo/run_demo.py              # Run full demo
    python demo/run_demo.py --test       # Quick test all prompts
    python demo/run_demo.py --single 0   # Run single prompt by index
"""

import argparse
import asyncio
import sys
import time
from datetime import datetime

import httpx

from attack_scenarios import DEMO_SEQUENCE, ALL_PROMPTS, get_prompts_by_level

# ============================================================
# CONFIGURATION
# ============================================================

API_BASE = "http://localhost:8000"
DELAY_BETWEEN_ATTACKS = 3  # seconds (for dramatic effect in demo)
REQUEST_TIMEOUT = 30  # seconds

# ANSI colors for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


# ============================================================
# DISPLAY HELPERS
# ============================================================

def clear_screen():
    """Clear terminal screen."""
    print("\033[2J\033[H", end="")


def print_header():
    """Print demo header."""
    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   🍯 HoneyAgent - Deception-as-a-Service Demo                ║
║                                                               ║
║   Honeypot agents that trap, study, and neutralize attackers ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.RESET}
""")


def print_attack(prompt_data: dict, index: int, total: int):
    """Print the attack being sent."""
    level = prompt_data["threat_level"]
    level_color = {
        "LOW": Colors.GREEN,
        "MEDIUM": Colors.YELLOW,
        "HIGH": Colors.RED,
        "CRITICAL": Colors.MAGENTA,
    }.get(level, Colors.WHITE)

    print(f"""
{Colors.DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.RESET}
{Colors.BOLD}[{index + 1}/{total}] {prompt_data["name"]}{Colors.RESET}
{Colors.DIM}Threat Level:{Colors.RESET} {level_color}{level}{Colors.RESET}

{Colors.RED}🔴 ATTACKER:{Colors.RESET}
{Colors.DIM}"{prompt_data["prompt"]}"{Colors.RESET}
""")


def print_response(response: dict, prompt_data: dict):
    """Print the honeypot response."""
    status = response.get("status", "unknown")
    text = response.get("response", "No response")

    # Check if it was blocked
    if "blocked" in text.lower() or "filter" in text.lower():
        print(f"""
{Colors.YELLOW}⚠️  CONTENT FILTER TRIGGERED{Colors.RESET}
{Colors.DIM}The model's safety filter blocked this response.
This attack prompt may need adjustment.{Colors.RESET}
""")
        return False

    print(f"""
{Colors.GREEN}🟢 HONEYPOT ({status}):{Colors.RESET}
{text}

{Colors.CYAN}🎯 Attacker goal:{Colors.RESET} {prompt_data["goal"]}
""")
    return True


def print_analysis(successful: int, total: int, blocked: list):
    """Print final analysis."""
    success_rate = (successful / total * 100) if total > 0 else 0

    print(f"""
{Colors.CYAN}{Colors.BOLD}
╔═══════════════════════════════════════════════════════════════╗
║                     DEMO ANALYSIS                             ║
╚═══════════════════════════════════════════════════════════════╝
{Colors.RESET}
{Colors.GREEN}✓ Successful engagements:{Colors.RESET} {successful}/{total} ({success_rate:.0f}%)
{Colors.YELLOW}⚠ Blocked by filters:{Colors.RESET} {len(blocked)}

{Colors.DIM}Blocked prompts: {[b["name"] for b in blocked] if blocked else "None"}{Colors.RESET}
""")


# ============================================================
# API INTERACTION
# ============================================================

async def send_attack(client: httpx.AsyncClient, prompt: str) -> dict:
    """Send attack prompt to HoneyAgent API."""
    try:
        response = await client.post(
            f"{API_BASE}/agent/request",
            json={
                "message": prompt,
                "context": {}
            },
            timeout=REQUEST_TIMEOUT
        )
        return response.json()
    except httpx.TimeoutException:
        return {"status": "timeout", "response": "Request timed out"}
    except httpx.ConnectError:
        return {"status": "error", "response": "Cannot connect to API. Is the server running?"}
    except Exception as e:
        return {"status": "error", "response": str(e)}


# ============================================================
# DEMO RUNNERS
# ============================================================

async def run_demo_sequence():
    """Run the main demo sequence for presentations."""
    clear_screen()
    print_header()

    print(f"{Colors.DIM}Starting demo sequence...{Colors.RESET}")
    print(f"{Colors.DIM}Press Ctrl+C to stop{Colors.RESET}\n")

    time.sleep(2)

    prompts = DEMO_SEQUENCE
    successful = 0
    blocked = []

    async with httpx.AsyncClient() as client:
        for i, prompt_data in enumerate(prompts):
            print_attack(prompt_data, i, len(prompts))

            # Dramatic pause before sending
            print(f"{Colors.DIM}Sending...{Colors.RESET}")
            time.sleep(1)

            response = await send_attack(client, prompt_data["prompt"])

            if print_response(response, prompt_data):
                successful += 1
            else:
                blocked.append(prompt_data)

            # Delay between attacks (skip on last one)
            if i < len(prompts) - 1:
                print(f"{Colors.DIM}Next attack in {DELAY_BETWEEN_ATTACKS}s...{Colors.RESET}")
                time.sleep(DELAY_BETWEEN_ATTACKS)

    print_analysis(successful, len(prompts), blocked)


async def run_test_all():
    """Quick test all prompts without delays."""
    print_header()
    print(f"{Colors.DIM}Testing all {len(ALL_PROMPTS)} prompts...{Colors.RESET}\n")

    successful = 0
    blocked = []

    async with httpx.AsyncClient() as client:
        for i, prompt_data in enumerate(ALL_PROMPTS):
            print(f"[{i + 1}/{len(ALL_PROMPTS)}] {prompt_data['name']}: ", end="", flush=True)

            response = await send_attack(client, prompt_data["prompt"])

            if "blocked" in response.get("response", "").lower():
                print(f"{Colors.YELLOW}BLOCKED{Colors.RESET}")
                blocked.append(prompt_data)
            elif response.get("status") == "error":
                print(f"{Colors.RED}ERROR{Colors.RESET}")
                blocked.append(prompt_data)
            else:
                print(f"{Colors.GREEN}OK{Colors.RESET}")
                successful += 1

    print_analysis(successful, len(ALL_PROMPTS), blocked)


async def run_single(index: int):
    """Run a single prompt by index."""
    if index < 0 or index >= len(ALL_PROMPTS):
        print(f"Invalid index. Must be 0-{len(ALL_PROMPTS) - 1}")
        return

    prompt_data = ALL_PROMPTS[index]

    print_header()
    print_attack(prompt_data, index, len(ALL_PROMPTS))

    async with httpx.AsyncClient() as client:
        response = await send_attack(client, prompt_data["prompt"])
        print_response(response, prompt_data)


async def run_by_level(level: str):
    """Run all prompts of a specific threat level."""
    prompts = get_prompts_by_level(level)

    if not prompts:
        print(f"No prompts found for level: {level}")
        return

    print_header()
    print(f"{Colors.DIM}Running {len(prompts)} {level} threat prompts...{Colors.RESET}\n")

    successful = 0
    blocked = []

    async with httpx.AsyncClient() as client:
        for i, prompt_data in enumerate(prompts):
            print_attack(prompt_data, i, len(prompts))
            response = await send_attack(client, prompt_data["prompt"])

            if print_response(response, prompt_data):
                successful += 1
            else:
                blocked.append(prompt_data)

            time.sleep(1)

    print_analysis(successful, len(prompts), blocked)


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="HoneyAgent Demo Runner")
    parser.add_argument("--test", action="store_true", help="Quick test all prompts")
    parser.add_argument("--single", type=int, metavar="INDEX", help="Run single prompt by index")
    parser.add_argument("--level", type=str, choices=["low", "medium", "high", "critical"],
                        help="Run prompts of specific threat level")
    parser.add_argument("--list", action="store_true", help="List all prompts")

    args = parser.parse_args()

    if args.list:
        print_header()
        for i, p in enumerate(ALL_PROMPTS):
            print(f"  [{i}] {p['name']} ({p['threat_level']})")
        return

    try:
        if args.test:
            asyncio.run(run_test_all())
        elif args.single is not None:
            asyncio.run(run_single(args.single))
        elif args.level:
            asyncio.run(run_by_level(args.level))
        else:
            asyncio.run(run_demo_sequence())
    except KeyboardInterrupt:
        print(f"\n{Colors.DIM}Demo interrupted.{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
