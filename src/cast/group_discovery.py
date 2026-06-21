from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

try:
    import pychromecast
    from pychromecast.const import CAST_TYPE_GROUP
    from pychromecast.discovery import CastBrowser, discover_chromecasts, stop_discovery
    from pychromecast.models import CastInfo, HostServiceInfo
except Exception:
    pychromecast = None
    CAST_TYPE_GROUP = "group"
    CastBrowser = None
    discover_chromecasts = None
    stop_discovery = None
    CastInfo = None
    HostServiceInfo = None


@dataclass(frozen=True)
class CastTarget:
    cast_info: CastInfo

    @property
    def uuid(self) -> str:
        return str(self.cast_info.uuid)

    @property
    def name(self) -> str:
        return self.cast_info.friendly_name or "Unknown"

    @property
    def host(self) -> str:
        return self.cast_info.host

    @property
    def port(self) -> int:
        return self.cast_info.port

    @property
    def model_name(self) -> str:
        return self.cast_info.model_name or ""

    @property
    def is_group(self) -> bool:
        return self.cast_info.cast_type == CAST_TYPE_GROUP


class CastGroupDiscovery:
    def __init__(
        self,
        groups_only: bool = True,
        discovery_timeout: float = 12.0,
        known_hosts: list[str] | None = None,
    ) -> None:
        self.groups_only = groups_only
        self.discovery_timeout = discovery_timeout
        self.known_hosts = known_hosts or []
        self.last_error: Optional[str] = None
        self._browser: Optional[CastBrowser] = None
        self._zconf = None
        self._lock = threading.Lock()

    @property
    def zconf(self):
        return self._zconf

    @staticmethod
    def _from_cast_info(cast_info: CastInfo) -> CastTarget:
        return CastTarget(cast_info=cast_info)

    @staticmethod
    def _filter_targets(targets: list[CastTarget], groups_only: bool) -> list[CastTarget]:
        if not groups_only:
            return sorted(targets, key=lambda t: (not t.is_group, t.name.lower()))

        only_groups = [target for target in targets if target.is_group]
        if only_groups:
            return sorted(only_groups, key=lambda t: t.name.lower())
        return sorted(targets, key=lambda t: (not t.is_group, t.name.lower()))

    def _stop_browser(self) -> None:
        if self._browser is not None and stop_discovery is not None:
            try:
                stop_discovery(self._browser)
            except Exception:
                pass
        self._browser = None

    def discover(self) -> list[CastTarget]:
        self.last_error = None
        if pychromecast is None or discover_chromecasts is None:
            self.last_error = "Run: pip install -r requirements.txt"
            return []

        with self._lock:
            self._stop_browser()
            try:
                hosts = self.known_hosts if self.known_hosts else None
                devices, browser = discover_chromecasts(
                    timeout=self.discovery_timeout,
                    known_hosts=hosts,
                )
                self._browser = browser
                self._zconf = browser.zc

                targets = [self._from_cast_info(device) for device in devices]
                deduped: dict[str, CastTarget] = {}
                for target in targets:
                    deduped[target.uuid] = target
                filtered = self._filter_targets(list(deduped.values()), self.groups_only)

                if not filtered and devices:
                    self.last_error = (
                        f"Found {len(devices)} device(s) but none matched the filter"
                    )
                elif not filtered:
                    self.last_error = (
                        "No Cast devices on network — check Wi-Fi and Google Home setup"
                    )

                return filtered
            except Exception as exc:
                self.last_error = str(exc)
                return []

    def fresh_cast_info(self, target: CastTarget) -> CastInfo:
        """Return the latest mDNS record for a target when the browser is still active."""
        if self._browser is None:
            return target.cast_info
        uuid = target.cast_info.uuid
        if uuid in self._browser.devices:
            return self._browser.devices[uuid]
        return target.cast_info

    def shutdown(self) -> None:
        with self._lock:
            self._stop_browser()
            self._zconf = None


def make_cast_target(
    uuid: str,
    name: str,
    host: str,
    port: int,
    is_group: bool,
    model_name: str,
) -> CastTarget:
    """Test helper for building a CastTarget without mDNS."""
    cast_type = CAST_TYPE_GROUP if is_group else "audio"
    cast_info = CastInfo(
        services={HostServiceInfo(host, port)},
        uuid=UUID(uuid),
        model_name=model_name,
        friendly_name=name,
        host=host,
        port=port,
        cast_type=cast_type,
        manufacturer=None,
    )
    return CastTarget(cast_info=cast_info)
