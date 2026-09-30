"""Controlled Hydra job construction for the CyberLab training environment.

This module deliberately accepts structured form values rather than a raw command.
Only explicitly supported services and pre-provisioned lab wordlists can be used.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from kali_executor import run_program


@dataclass(frozen=True)
class HydraService:
    label: str
    module: str
    default_port: int


# Keep this intentionally small. Add a service only after it has been tested in
# the lab and its use has been approved.
SERVICES = {
    "ssh": HydraService("SSH", "ssh", 22),
    "ftp": HydraService("FTP", "ftp", 21),
}

# These files must be provisioned in the Kali VM. The web UI never accepts an
# arbitrary host path or an uploaded wordlist.
WORDLISTS = {
    "demo": {
        "label": "CyberLab demo credentials",
        "users": "/opt/cyberlab/wordlists/demo-users.txt",
        "passwords": "/opt/cyberlab/wordlists/demo-passwords.txt",
    },
}


def validate_target(target: str, permitted_targets: set[str]) -> str:
    """Return a validated, online-device target or raise ValueError."""
    try:
        normalized = str(ipaddress.ip_address(target.strip()))
    except ValueError as exc:
        raise ValueError("Select a valid connected-device IP address.") from exc

    if normalized not in permitted_targets:
        raise ValueError("The target must be an online device registered in CyberLab.")
    return normalized


def build_command(target: str, service_key: str, port: str, wordlist_key: str) -> list[str]:
    """Build a conservative Hydra command from allowlisted values."""
    service = SERVICES.get(service_key)
    wordlist = WORDLISTS.get(wordlist_key)
    if not service or not wordlist:
        raise ValueError("Select a supported service and lab credential set.")

    try:
        parsed_port = int(port)
    except (TypeError, ValueError) as exc:
        raise ValueError("Port must be a number between 1 and 65535.") from exc
    if not 1 <= parsed_port <= 65535:
        raise ValueError("Port must be a number between 1 and 65535.")

    # One task, a short wait, and stop-on-first-match keep this appropriate for
    # a small, authorized lab and avoid a high-volume credential attack.
    return [
        "/usr/bin/hydra",
        "-L", wordlist["users"],
        "-P", wordlist["passwords"],
        "-s", str(parsed_port),
        "-t", "1",
        "-W", "3",
        "-f",
        target,
        service.module,
    ]


def command_preview(command: list[str]) -> str:
    """Render the allowlisted command for review without shell execution."""
    return " ".join(command)


def run_hydra(command: list[str]) -> tuple[str, str]:
    """Run the reviewed command inside the configured Kali VM."""
    return run_program(command[0], *command[1:])
