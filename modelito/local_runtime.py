"""Local runtime profile helpers.

Profiles express deployment intent without claiming that one local backend is
universally fastest.  ``portable`` uses Ollama as the common cross-platform
path.  ``mac-performance`` uses Apple-Silicon-native backends, preferring oMLX
and retaining Ollama as a fallback.  Applications can override the order after
benchmarking representative workloads.
"""

from __future__ import annotations

from typing import List, Optional

LOCAL_PROFILE_AUTO = "auto"
LOCAL_PROFILE_PORTABLE = "portable"
LOCAL_PROFILE_MAC_PERFORMANCE = "mac-performance"
LOCAL_PROFILES = (
    LOCAL_PROFILE_AUTO,
    LOCAL_PROFILE_PORTABLE,
    LOCAL_PROFILE_MAC_PERFORMANCE,
)

_ALIASES = {
    "mac": LOCAL_PROFILE_MAC_PERFORMANCE,
    "macos": LOCAL_PROFILE_MAC_PERFORMANCE,
    "apple": LOCAL_PROFILE_MAC_PERFORMANCE,
    "apple-silicon": LOCAL_PROFILE_MAC_PERFORMANCE,
    "apple_silicon": LOCAL_PROFILE_MAC_PERFORMANCE,
    "cross-platform": LOCAL_PROFILE_PORTABLE,
    "cross_platform": LOCAL_PROFILE_PORTABLE,
}


def normalize_local_profile(profile: Optional[str]) -> str:
    """Return the canonical local-runtime profile name.

    ``None`` resolves to ``auto``.  Unknown names fail explicitly rather than
    silently changing provider-selection behaviour.
    """

    value = str(profile or LOCAL_PROFILE_AUTO).strip().lower()
    value = _ALIASES.get(value, value)
    if value not in LOCAL_PROFILES:
        allowed = ", ".join(LOCAL_PROFILES)
        raise ValueError(f"Unknown local runtime profile: {profile!r}. Expected one of: {allowed}")
    return value


def local_provider_candidates(
    profile: Optional[str], *, is_macos_apple_silicon: bool
) -> List[str]:
    """Return the ordered local providers for *profile*.

    ``mac-performance`` is intentionally restricted to Apple Silicon.  The
    ordering is a practical default, not a benchmark guarantee.
    """

    normalized = normalize_local_profile(profile)
    if normalized == LOCAL_PROFILE_AUTO:
        normalized = (
            LOCAL_PROFILE_MAC_PERFORMANCE
            if is_macos_apple_silicon
            else LOCAL_PROFILE_PORTABLE
        )

    if normalized == LOCAL_PROFILE_PORTABLE:
        return ["ollama"]

    if not is_macos_apple_silicon:
        raise ValueError(
            "The mac-performance local runtime profile requires macOS on Apple Silicon. "
            "Use profile='portable' on other platforms."
        )
    return ["omlx", "ollama"]
