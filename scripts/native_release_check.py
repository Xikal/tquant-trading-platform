#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION.json"
BUILD_GRADLE = ROOT / "frontend" / "android" / "app" / "build.gradle"
ANDROID_PUBLIC = ROOT / "frontend" / "android" / "app" / "src" / "main" / "assets" / "public"
ANDROID_MAIN_MANIFEST = ROOT / "frontend" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
ANDROID_MAIN_NETWORK_CONFIG = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res" / "xml" / "network_security_config.xml"
ANDROID_DEBUG_MANIFEST = ROOT / "frontend" / "android" / "app" / "src" / "debug" / "AndroidManifest.xml"


def main() -> int:
    version = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    expected_code = int(version["build_number"])
    expected_name = str(version["version"])
    errors: list[str] = []

    gradle_text = BUILD_GRADLE.read_text(encoding="utf-8")
    if f"versionCode {expected_code}" not in gradle_text:
        errors.append(f"Android versionCode is not {expected_code}")
    if f'versionName "{expected_name}"' not in gradle_text:
        errors.append(f"Android versionName is not {expected_name}")

    secret_patterns = ("keystore.properties", ".jks", ".keystore")
    leaked = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "frontend" / "android").rglob("*")
        if path.is_file() and any(str(path).endswith(pattern) for pattern in secret_patterns)
    ]
    if leaked:
        errors.append("Android signing files must not be committed or packaged: " + ", ".join(leaked))

    errors.extend(_cleartext_security_errors())

    if not ANDROID_PUBLIC.exists():
        errors.append("Android bundled assets are missing. Run `cd frontend && npm run build:native && npx cap sync android`.")
    else:
        js_files = list(ANDROID_PUBLIC.rglob("*.js"))
        if not js_files:
            errors.append("Android bundled assets contain no JavaScript files. Run `cd frontend && npm run build:native && npx cap sync android`.")
        else:
            js_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in js_files)
            version_match = re.search(
                r"var\s+[A-Za-z_$][\w$]*\s*=\s*(\d+)\s*,[A-Za-z_$][\w$]*=`tquant\.dismissed_android_update`",
                js_text,
            )
            if not version_match:
                errors.append("Native bundled update version marker was not found. Run `cd frontend && npm run build:native && npx cap sync android`.")
            elif int(version_match.group(1)) != expected_code:
                errors.append(
                    f"Native bundled update version is {version_match.group(1)}, expected {expected_code}. "
                    "Run `cd frontend && npm run build:native && npx cap sync android`."
                )

    if errors:
        for error in errors:
            print(f"native-release-check:error {error}", file=sys.stderr)
        return 1
    print(f"native-release-check:ok version={expected_name} build_number={expected_code}")
    return 0


def _cleartext_security_errors() -> list[str]:
    errors: list[str] = []
    if not ANDROID_MAIN_MANIFEST.exists():
        return ["Android main manifest is missing."]
    if not ANDROID_MAIN_NETWORK_CONFIG.exists():
        return ["Android release network security config is missing."]
    main_text = ANDROID_MAIN_MANIFEST.read_text(encoding="utf-8", errors="ignore")
    if 'usesCleartextTraffic="true"' in main_text:
        errors.append("Android main/release manifest must not enable usesCleartextTraffic=true.")
    try:
        manifest_root = ElementTree.fromstring(main_text)
        namespace = "{http://schemas.android.com/apk/res/android}"
        applications = manifest_root.findall("application")
        if not applications:
            errors.append("Android main manifest has no <application> node.")
        for application in applications:
            value = application.attrib.get(f"{namespace}usesCleartextTraffic", "").strip().lower()
            if value == "true":
                errors.append("Android main/release application enables cleartext traffic.")
            config = application.attrib.get(f"{namespace}networkSecurityConfig", "")
            if config != "@xml/network_security_config":
                errors.append("Android main/release application must use @xml/network_security_config.")
    except ElementTree.ParseError as exc:
        errors.append(f"Android main manifest is not valid XML: {exc}")

    config_text = ANDROID_MAIN_NETWORK_CONFIG.read_text(encoding="utf-8", errors="ignore")
    if 'cleartextTrafficPermitted="true"' in config_text:
        errors.append("Android main/release network security config permits cleartext traffic.")
    if 'cleartextTrafficPermitted="false"' not in config_text:
        errors.append("Android main/release network security config must explicitly disable cleartext traffic.")
    if ANDROID_DEBUG_MANIFEST.exists():
        debug_text = ANDROID_DEBUG_MANIFEST.read_text(encoding="utf-8", errors="ignore")
        if 'usesCleartextTraffic="true"' in debug_text:
            # Debug overlay is allowed to keep localhost/dev-server workflows working.
            return errors
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
