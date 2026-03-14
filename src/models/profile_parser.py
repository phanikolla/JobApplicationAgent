"""
Parses the applicant_profile.md into a structured dictionary
that the LLM can consume when filling application forms.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)


def parse_profile(profile_path: str = "applicant_profile.md") -> dict:
    """
    Parse the applicant profile markdown into a structured dict.
    Returns a flat dict of key-value pairs for easy LLM consumption.
    """
    if not os.path.exists(profile_path):
        logger.error(f"Profile file not found: {profile_path}")
        return {}

    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    profile = {}
    current_section = "general"

    for line in content.splitlines():
        line = line.strip()

        # Skip empty lines and the title
        if not line or line.startswith("# ") or line.startswith("All details"):
            continue

        # Detect section headers
        if line.startswith("## "):
            current_section = line[3:].strip().lower().replace(" ", "_")
            continue

        # Parse "- Key: Value" lines
        match = re.match(r"^-\s+(.+?):\s*(.+)$", line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_").replace("/", "_")
            value = match.group(2).strip()
            # Store with section prefix for clarity
            profile[f"{current_section}.{key}"] = value
            # Also store without prefix for flexible matching
            profile[key] = value

    logger.info(f"Parsed {len(profile)} fields from applicant profile")
    return profile


def get_profile_as_text(profile_path: str = "applicant_profile.md") -> str:
    """
    Returns the raw markdown content for inclusion in LLM prompts.
    """
    if not os.path.exists(profile_path):
        logger.error(f"Profile file not found: {profile_path}")
        return ""

    with open(profile_path, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import pprint
    profile = parse_profile()
    pprint.pprint(profile)
