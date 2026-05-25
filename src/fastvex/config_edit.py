from __future__ import annotations

from .storage import ValidationError


def replace_active_route_in_text(text: str, route_set: str, route_key: str) -> str:
    """Text-based replacement to keep YAML comments/formatting intact."""
    lines = text.splitlines()
    in_active = False
    found = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "activeRoute:":
            in_active = True
            continue
        if in_active:
            if stripped and not line.startswith("  "):
                break
            key_prefix = f"  {route_set}:"
            if line.startswith(key_prefix):
                lines[idx] = f"  {route_set}: {route_key}"
                found = True
                break
    if not found:
        raise ValidationError(f"failed to update activeRoute.{route_set} in config file")
    return "\n".join(lines) + "\n"
