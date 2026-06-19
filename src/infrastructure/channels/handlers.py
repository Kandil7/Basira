"""
Multi-channel CX — Email and social media channel handlers.

Extends the CX agent to support multiple communication channels
beyond web chat and WhatsApp.
"""

from typing import Any

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class ChannelConfig(BaseModel):
    """Configuration for a communication channel."""

    channel_id: str
    channel_name: str
    channel_type: str = Field(description="email, whatsapp, web, social, api")
    is_active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class ChannelMessage(BaseModel):
    """Message from a communication channel."""

    channel_id: str
    channel_type: str
    sender_id: str
    sender_name: str | None = None
    content: str
    message_id: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelResponse(BaseModel):
    """Response to be sent back through a channel."""

    channel_id: str
    recipient_id: str
    content: str
    message_type: str = "text"  # text, image, file
    metadata: dict[str, Any] = Field(default_factory=dict)


# Supported channels
SUPPORTED_CHANNELS = {
    "web": "Web Chat",
    "whatsapp": "WhatsApp Business",
    "email": "Email",
    "telegram": "Telegram",
    "social": "Social Media",
    "api": "REST API",
}


def get_channel_config(channel_type: str) -> ChannelConfig | None:
    """
    Get channel configuration by type.

    Args:
        channel_type: Type of channel (web, whatsapp, email, etc.)

    Returns:
        ChannelConfig if supported, None otherwise.
    """
    if channel_type not in SUPPORTED_CHANNELS:
        return None

    return ChannelConfig(
        channel_id=channel_type,
        channel_name=SUPPORTED_CHANNELS[channel_type],
        channel_type=channel_type,
    )


def format_response_for_channel(
    response: str,
    channel_type: str,
) -> str:
    """
    Format response text for a specific channel.

    Some channels have character limits or formatting requirements.

    Args:
        response: Raw response text
        channel_type: Target channel

    Returns:
        Formatted response text.
    """
    if channel_type == "whatsapp":
        # WhatsApp has a 4096 character limit
        if len(response) > 4000:
            response = response[:3997] + "..."

    elif channel_type == "email":
        # Email can be longer, but add greeting
        if not response.startswith("مرحباً"):
            response = f"مرحباً،\n\n{response}\n\nمع تحياتنا،\nفريق خدمة العملاء"

    elif channel_type == "telegram":
        # Telegram supports markdown
        pass  # No special formatting needed

    return response


def extract_channel_metadata(
    channel_type: str,
    raw_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract channel-specific metadata from raw request data.

    Args:
        channel_type: Type of channel
        raw_metadata: Raw metadata from the request

    Returns:
        Extracted metadata specific to the channel.
    """
    metadata = {"channel_type": channel_type}

    if channel_type == "whatsapp":
        metadata["customer_phone"] = raw_metadata.get("customer_phone", "")
        metadata["message_id"] = raw_metadata.get("message_id", "")

    elif channel_type == "email":
        metadata["customer_email"] = raw_metadata.get("customer_email", "")
        metadata["subject"] = raw_metadata.get("subject", "")

    elif channel_type == "telegram":
        metadata["chat_id"] = raw_metadata.get("chat_id", "")
        metadata["message_id"] = raw_metadata.get("message_id", "")

    elif channel_type == "social":
        metadata["platform"] = raw_metadata.get("platform", "")
        metadata["post_id"] = raw_metadata.get("post_id", "")

    return metadata
