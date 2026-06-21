from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

try:
    import pychromecast
    from pychromecast.const import CAST_TYPE_GROUP
    from pychromecast.discovery import CastBrowser, SimpleCastListener
    from pychromecast.models import CastInfo, HostServiceInfo
    import zeroconf as zeroconf_module
except Exception:
    pychromecast = None
    CAST_TYPE_GROUP = "group"
    CastBrowser = None
    SimpleCastListener = None
    CastInfo = None
    HostServiceInfo = None
    zeroconf_module = None


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
        groups_only: bool = False,
        discovery_timeout: float = 12.0,
        known_hosts: list[str] | None = None,
    ) -> None:
        self.groups_only = groups_only
        self.discovery_timeout = discovery_timeout
        self.known_hosts = known_hosts or []
        self.last_error: Optional[str] = None
        self._browser: Optional[CastBrowser] = None
        self._zconf = None
        self._started = False
        self._lock = threading.Lock()

    @property
    def zconf(self):
        return self._zconf

    def _ensure_browser(self) -> bool:
        """Start a persistent background browser whose device list grows over time."""
        if self._started and self._browser is not None:
            return True
        if (
            pychromecast is None
            or CastBrowser is None
            or SimpleCastListener is None
            or zeroconf_module is None
        ):
            return False

        self._zconf = zeroconf_module.Zeroconf()
        listener = SimpleCastListener()
        known = self.known_hosts if self.known_hosts else None
        try:
            self._browser = CastBrowser(listener, self._zconf, known_hosts=known)
        except TypeError:
            self._browser = CastBrowser(listener, self._zconf)
        self._browser.start_discovery()
        self._started = True
        return True

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
        if self._browser is not None:
            try:
                self._browser.stop_discovery()
            except Exception:
                pass
        self._browser = None
        if self._zconf is not None:
            try:
                self._zconf.close()
            except Exception:
                pass
        self._zconf = None
        self._started = False

    def _read_browser_targets(self) -> list[CastTarget]:
        if not self._ensure_browser():
            self.last_error = "Run: pip install -r requirements.txt"
            return []

        devices = list(self._browser.devices.values())
        deduped: dict[str, CastTarget] = {}
        for device in devices:
            target = self._from_cast_info(device)
            deduped[target.uuid] = target
        filtered = self._filter_targets(list(deduped.values()), self.groups_only)

        if devices and not filtered:
            self.last_error = (
                f"Found {len(devices)} on LAN but filter hid them "
                "(set GOOGLE_GROUPS_ONLY=false in .env)"
            )

        return filtered

    def discover(self, wait_seconds: float | None = None) -> list[CastTarget]:
        """Read Cast devices from the persistent browser (optionally wait for mDNS)."""
        self.last_error = None
        if pychromecast is None or CastBrowser is None:
            self.last_error = "Run: pip install -r requirements.txt"
            return []

        wait = wait_seconds if wait_seconds is not None else 0.0
        if wait <= 0:
            with self._lock:
                try:
                    return self._read_browser_targets()
                except Exception as exc:
                    self.last_error = str(exc)
                    return []

        deadline = time.time() + wait
        best: list[CastTarget] = []
        with self._lock:
            try:
                while time.time() < deadline:
                    current = self._read_browser_targets()
                    if len(current) > len(best):
                        best = list(current)
                    time.sleep(0.4)
                return best if best else self._read_browser_targets()
            except Exception as exc:
                self.last_error = str(exc)
                return best

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
