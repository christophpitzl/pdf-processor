"""
Wake-on-LAN (WOL) utilities for waking up the Ollama server.

Provides functions to send magic packets and wait for the Ollama server
to become available after wake-up.
"""

import socket
import time
from typing import Optional

import httpx
from loguru import logger


def wake_on_lan(
    mac_address: str,
    host: str = "255.255.255.255",
    port: int = 9,
) -> bool:
    """Send a Wake-on-LAN magic packet to wake up a device.

    Args:
        mac_address: MAC address of the target device (e.g. "AA:BB:CC:DD:EE:FF").
        host: Broadcast IP address. Defaults to "255.255.255.255".
        port: UDP port for the magic packet. Defaults to 9.

    Returns:
        True if the packet was sent successfully, False otherwise.
    """
    # Normalize MAC address: remove separators and convert to uppercase
    clean_mac = mac_address.replace("-", "").replace(":", "").replace(".", "")

    if len(clean_mac) != 12:
        logger.error(f"Invalid MAC address format: {mac_address}")
        return False

    # Build the magic packet: 6x 0xFF + 16x MAC address
    mac_bytes = bytes(int(clean_mac[i : i + 2], 16) for i in range(0, 12, 2))
    header = b"\xff" * 6 + mac_bytes * 16

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(header, (host, port))
        sock.close()
        logger.info(
            f"Sent WOL magic packet to {mac_address} via {host}:{port}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send WOL magic packet: {e}")
        return False


def wait_for_ollama(
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "granite4.1:3b",
    max_retries: int = 10,
    retry_delay: float = 5.0,
) -> bool:
    """Wait for the Ollama server to become available.

    Repeatedly attempts to reach the Ollama API until it responds
    or the maximum number of retries is reached.

    Args:
        ollama_base_url: Base URL of the Ollama API server.
        ollama_model: Model name to use for the health check request.
        max_retries: Maximum number of retry attempts.
        retry_delay: Seconds to wait between retries.

    Returns:
        True if the Ollama server became available, False otherwise.
    """
    logger.info(
        f"Waiting for Ollama server at {ollama_base_url} "
        f"(model: {ollama_model})..."
    )

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(
                timeout=httpx.Timeout(5.0, connect=2.0)
            ) as client:
                response = client.post(
                    f"{ollama_base_url}/api/show",
                    json={"name": ollama_model},
                )
                if response.status_code in (200, 404):
                    # 200 = model found, 404 = model not found but server is up
                    logger.success("Ollama server is now available")
                    return True
        except httpx.RequestError:
            pass

        remaining = max_retries - attempt
        if remaining > 0:
            logger.debug(
                f"Ollama not ready yet, retrying in {retry_delay}s "
                f"({remaining} retries remaining)"
            )
        else:
            logger.warning("Ollama server did not become ready in time")

        time.sleep(retry_delay)

    return False
