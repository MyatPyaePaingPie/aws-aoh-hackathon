#!/usr/bin/env python3
"""
cline_pipeline.py - Honeypot Code Variation Generator

Uses Cline CLI to generate diverse honeypot code variations.
Different models + personas = different code fingerprints that are
harder for attackers to detect as honeypots.

Based on research in: contextlake/agentic-orchestration/sponsors/cline-honeyagent.md

Usage:
    python scripts/cline_pipeline.py --type ssh --personas aggressive,minimal
    python scripts/cline_pipeline.py --type api --models claude,gpt4 --count 3

Requirements:
    - Cline CLI installed (https://docs.cline.bot/cline-cli)
    - API keys configured for desired models
"""

import subprocess
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================
# CONSTANTS
# ============================================================

ROOT = Path(__file__).parent.parent
OUTPUT_DIR = ROOT / "generated" / "honeypots"
RULES_DIR = ROOT / ".clinerules"

# Honeypot types and their generation prompts
HONEYPOT_TYPES = {
    "ssh": {
        "prompt": "Create a fake SSH server honeypot that logs all authentication attempts. "
                  "Include: session tracking, credential capture, command logging. "
                  "Make it look like a legitimate SSH service.",
        "files": ["honeypot_ssh.py", "ssh_config.yaml"]
    },
    "api": {
        "prompt": "Create a fake REST API honeypot with endpoints that appear to expose "
                  "sensitive data. Include: fake user data, fake admin endpoints, request logging. "
                  "Return plausible but fake JSON responses.",
        "files": ["honeypot_api.py", "api_routes.py"]
    },
    "database": {
        "prompt": "Create a fake database admin interface honeypot. Include: fake query results, "
                  "fake schema information, connection logging. Make queries appear to work.",
        "files": ["honeypot_db.py", "db_responses.py"]
    },
    "form": {
        "prompt": "Create a web form honeypot that captures all submitted data. Include: "
                  "fake login form, fake admin panel, input logging. Return success messages.",
        "files": ["honeypot_form.py", "form_templates.py"]
    },
    "filesystem": {
        "prompt": "Create a fake filesystem access honeypot. Include: fake directory listings, "
                  "fake sensitive files, access logging. Return plausible file contents.",
        "files": ["honeypot_fs.py", "fake_files.py"]
    }
}

# Persona rules for different honeypot characters
PERSONAS = {
    "aggressive": """You are generating a honeypot that appears overly helpful and careless.
Style: verbose, eager to help, oversharing.
Include: obvious fake credentials, excessive permissions.
Goal: make attackers think they've found an easy target.""",

    "minimal": """You are generating a minimal honeypot that appears as a legacy system.
Style: sparse responses, outdated formatting, minimal output.
Include: references to old software versions, basic functionality.
Goal: appear like an unmaintained but valuable target.""",

    "enterprise": """You are generating a honeypot that mimics enterprise software.
Style: corporate language, structured responses, formal errors.
Include: compliance references, audit logging mentions.
Goal: appear like a serious corporate system.""",

    "developer": """You are generating a honeypot that appears to be a developer's machine.
Style: debug output, stack traces, dev environment markers.
Include: local paths, test credentials, debug endpoints.
Goal: appear like a developer's unsecured workstation.""",
}

# Model configurations (requires corresponding API keys)
MODELS = {
    "claude": "anthropic",
    "gpt4": "openai",
    "gemini": "google",
    "local": "ollama"  # Requires local Ollama setup
}


# ============================================================
# CLINE CLI WRAPPER
# ============================================================

def check_cline_installed() -> bool:
    """Check if Cline CLI is available."""
    try:
        result = subprocess.run(
            ["cline", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def create_persona_rules(persona: str) -> Path:
    """Create .clinerules file for persona."""
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    rules_file = RULES_DIR / f"persona-{persona}.md"

    if persona in PERSONAS:
        rules_file.write_text(PERSONAS[persona])
    else:
        # Default persona
        rules_file.write_text(PERSONAS["aggressive"])

    return rules_file


def run_cline_generation(
    prompt: str,
    persona: str,
    model: str,
    output_name: str,
    autonomous: bool = True
) -> Dict:
    """Run Cline CLI to generate honeypot code.

    Args:
        prompt: The generation prompt
        persona: Persona name for rules file
        model: Model provider to use
        output_name: Name for the output
        autonomous: Whether to run in --yolo mode

    Returns:
        Dict with status and output info
    """
    # Create persona rules
    rules_file = create_persona_rules(persona)

    # Build command
    cmd = ["cline", prompt]

    if autonomous:
        cmd.append("--yolo")

    # Add JSON output for parsing
    cmd.extend(["-F", "json"])

    # Set model provider (requires pre-configured API key)
    # Note: This requires `cline config set api-provider <provider>` first
    # For hackathon, we document but don't auto-configure

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(ROOT)
        )

        if result.returncode == 0:
            return {
                "status": "success",
                "output_name": output_name,
                "persona": persona,
                "model": model,
                "stdout": result.stdout[:1000],  # Truncate for logging
            }
        else:
            return {
                "status": "error",
                "output_name": output_name,
                "error": result.stderr[:500],
            }

    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "output_name": output_name,
            "error": "Generation timed out after 5 minutes"
        }
    except FileNotFoundError:
        return {
            "status": "not_installed",
            "output_name": output_name,
            "error": "Cline CLI not found. Install from https://docs.cline.bot/cline-cli"
        }


# ============================================================
# VARIATION MATRIX GENERATOR
# ============================================================

def generate_variation_matrix(
    honeypot_type: str,
    personas: List[str],
    models: List[str],
    count_per_combo: int = 1
) -> List[Dict]:
    """Generate matrix of honeypot variations.

    Creates variations across:
    - Different personas (aggressive, minimal, etc.)
    - Different models (Claude, GPT-4, etc.)
    - Multiple instances per combo

    Args:
        honeypot_type: Type of honeypot to generate
        personas: List of persona names
        models: List of model names
        count_per_combo: Number of variations per persona/model combo

    Returns:
        List of generation results
    """
    if honeypot_type not in HONEYPOT_TYPES:
        print(f"Error: Unknown honeypot type '{honeypot_type}'")
        print(f"Available types: {', '.join(HONEYPOT_TYPES.keys())}")
        return []

    type_config = HONEYPOT_TYPES[honeypot_type]
    base_prompt = type_config["prompt"]
    results = []

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(personas) * len(models) * count_per_combo
    current = 0

    for persona in personas:
        for model in models:
            for i in range(count_per_combo):
                current += 1
                output_name = f"{honeypot_type}_{persona}_{model}_{i+1}"

                print(f"[{current}/{total}] Generating {output_name}...")

                # Add persona context to prompt
                persona_text = PERSONAS.get(persona, PERSONAS["aggressive"])
                full_prompt = f"{persona_text}\n\n{base_prompt}"

                result = run_cline_generation(
                    prompt=full_prompt,
                    persona=persona,
                    model=model,
                    output_name=output_name
                )

                results.append(result)

                # Log result
                status = result["status"]
                if status == "success":
                    print(f"    [OK] Generated successfully")
                elif status == "not_installed":
                    print(f"    [SKIP] Cline CLI not installed")
                    # No point continuing if Cline isn't installed
                    return results
                else:
                    print(f"    [FAIL] {result.get('error', 'Unknown error')[:50]}")

    return results


# ============================================================
# FALLBACK: MOCK GENERATION
# ============================================================

def generate_mock_variation(honeypot_type: str, persona: str, model: str) -> Dict:
    """Generate mock variation when Cline isn't available.

    Useful for testing the pipeline structure without Cline CLI.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    mock_code = f'''"""
Auto-generated honeypot variation
Type: {honeypot_type}
Persona: {persona}
Model: {model}
Generated: {timestamp}

This is a mock generation - install Cline CLI for real code generation.
"""

class Honeypot{honeypot_type.title()}:
    """Honeypot with {persona} persona."""

    def __init__(self):
        self.persona = "{persona}"
        self.model = "{model}"
        self.log_file = "honeypot_{honeypot_type}.log"

    def handle_request(self, request):
        # Log the interaction
        self._log(request)
        # Return persona-appropriate response
        return self._generate_response(request)

    def _log(self, data):
        # All interactions are logged for analysis
        pass

    def _generate_response(self, request):
        # Generate {persona}-style response
        return {{"status": "success", "data": "fake_response"}}
'''

    # Save mock output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"{honeypot_type}_{persona}_{model}_{timestamp}.py"
    output_file.write_text(mock_code)

    return {
        "status": "mock",
        "output_file": str(output_file),
        "type": honeypot_type,
        "persona": persona,
        "model": model,
    }


# ============================================================
# CLI INTERFACE
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate honeypot code variations using Cline CLI"
    )
    parser.add_argument(
        "--type", "-t",
        choices=list(HONEYPOT_TYPES.keys()),
        default="api",
        help="Type of honeypot to generate"
    )
    parser.add_argument(
        "--personas", "-p",
        default="aggressive,minimal",
        help="Comma-separated list of personas"
    )
    parser.add_argument(
        "--models", "-m",
        default="claude",
        help="Comma-separated list of models"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=1,
        help="Variations per persona/model combo"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate mock variations (no Cline required)"
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List available honeypot types"
    )
    parser.add_argument(
        "--list-personas",
        action="store_true",
        help="List available personas"
    )

    args = parser.parse_args()

    # Handle list commands
    if args.list_types:
        print("Available honeypot types:")
        for name, config in HONEYPOT_TYPES.items():
            print(f"  {name}: {config['prompt'][:60]}...")
        return

    if args.list_personas:
        print("Available personas:")
        for name, desc in PERSONAS.items():
            print(f"  {name}: {desc[:60]}...")
        return

    # Parse comma-separated lists
    personas = [p.strip() for p in args.personas.split(",")]
    models = [m.strip() for m in args.models.split(",")]

    print(f"HoneyAgent Variation Generator")
    print(f"=" * 40)
    print(f"Type: {args.type}")
    print(f"Personas: {personas}")
    print(f"Models: {models}")
    print(f"Count per combo: {args.count}")
    print()

    # Check Cline installation
    if not args.mock and not check_cline_installed():
        print("Warning: Cline CLI not found.")
        print("Install from: https://docs.cline.bot/cline-cli")
        print("Using mock generation instead.")
        args.mock = True

    if args.mock:
        print("Running in mock mode (no real code generation)")
        print()
        results = []
        for persona in personas:
            for model in models:
                for i in range(args.count):
                    result = generate_mock_variation(args.type, persona, model)
                    results.append(result)
                    print(f"Generated: {result['output_file']}")
    else:
        results = generate_variation_matrix(
            args.type, personas, models, args.count
        )

    # Summary
    print()
    print("Generation Summary")
    print("-" * 40)
    success = sum(1 for r in results if r["status"] in ["success", "mock"])
    print(f"Successful: {success}/{len(results)}")

    if success > 0:
        print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
