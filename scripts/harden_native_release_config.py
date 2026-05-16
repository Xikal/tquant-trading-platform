#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_NETWORK_CONFIG = ROOT / "frontend/android/app/src/main/res/xml/network_security_config.xml"
ANDROID_CONFIG_XML = ROOT / "frontend/android/app/src/main/res/xml/config.xml"
IOS_CONFIG_XML = ROOT / "frontend/ios/App/App/config.xml"

PRODUCTION_ORIGINS = (
    "https://weisilianghua.cloud",
    "https://www.weisilianghua.cloud",
)


def main() -> int:
    _write_android_network_security()
    _write_access_config(ANDROID_CONFIG_XML)
    _write_access_config(IOS_CONFIG_XML)
    print("native-release-config:hardened")
    return 0


def _write_android_network_security() -> None:
    ANDROID_NETWORK_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ANDROID_NETWORK_CONFIG.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="false" />
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">weisilianghua.cloud</domain>
    </domain-config>
</network-security-config>
""",
        encoding="utf-8",
    )


def _write_access_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    access_lines = "\n".join(f'  <access origin="{origin}" />' for origin in PRODUCTION_ORIGINS)
    path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<widget version="1.0.0" xmlns="http://www.w3.org/ns/widgets" xmlns:cdv="http://cordova.apache.org/ns/1.0">
{access_lines}
</widget>
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
