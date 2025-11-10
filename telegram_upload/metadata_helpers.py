"""
Helper functions for safely extracting metadata from media files.

This module provides utilities to safely access metadata from various
media formats, handling edge cases like MKV files that use private
attributes in the hachoir library.
"""
import logging
from typing import Any, Optional


logger = logging.getLogger(__name__)


def get_video_metadata_stream(metadata: Any) -> Optional[Any]:
    """
    Safely extract video metadata stream from file metadata.

    For most video formats, the main metadata object contains video information.
    For MKV files (which use MultipleMetadata), we need to find the video stream
    within the container's multiple streams.

    Args:
        metadata: Metadata object from hachoir (can be various types)

    Returns:
        Video metadata stream if found, otherwise the original metadata object.
        Returns None if metadata is None.

    Note:
        This function handles the special case of MKV files which store metadata
        in a private _MultipleMetadata__groups attribute. While accessing private
        attributes is not ideal, it's necessary for MKV support until hachoir
        provides a public API.
    """
    if metadata is None:
        return None

    # Try to get meta_groups using private attribute (for MKV files)
    meta_groups = None
    try:
        # Check if this is a MultipleMetadata object (typical for MKV)
        if hasattr(metadata, '_MultipleMetadata__groups'):
            logger.debug("Detected MultipleMetadata (likely MKV file), extracting video stream")
            meta_groups = metadata._MultipleMetadata__groups  # type: ignore
    except (AttributeError, TypeError) as e:
        logger.debug(f"Could not access metadata groups: {e}")
        return metadata

    # If we have multiple streams and the main metadata lacks width,
    # find the video stream (handles MKV containers)
    if meta_groups is not None:
        try:
            # Check if main metadata has width (simple video file)
            if metadata.has('width'):
                return metadata

            # Find the video stream in the container
            if hasattr(meta_groups, '_key_list'):
                video_keys = [k for k in meta_groups._key_list if k.startswith('video')]  # type: ignore
                if video_keys:
                    video_stream = meta_groups[video_keys[0]]  # type: ignore
                    logger.debug(f"Found video stream: {video_keys[0]}")
                    return video_stream
        except (AttributeError, KeyError, IndexError, TypeError) as e:
            logger.warning(f"Error extracting video stream from metadata: {e}")
            return metadata

    return metadata


def metadata_has(metadata: Any, key: str) -> bool:
    """
    Safely check if metadata has a specific key.

    Args:
        metadata: Metadata object from hachoir
        key: Key name to check

    Returns:
        True if metadata has the key, False otherwise
    """
    if metadata is None:
        return False

    try:
        return metadata.has(key) if hasattr(metadata, 'has') else False
    except (AttributeError, TypeError):
        return False


def metadata_get(metadata: Any, key: str, default: Any = None) -> Any:
    """
    Safely get a value from metadata.

    Args:
        metadata: Metadata object from hachoir
        key: Key name to retrieve
        default: Default value if key not found

    Returns:
        Value for the key, or default if not found
    """
    if metadata is None:
        return default

    try:
        if hasattr(metadata, 'has') and metadata.has(key):
            return metadata.get(key)
    except (AttributeError, TypeError, KeyError):
        pass

    return default
