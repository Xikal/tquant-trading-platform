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
ANDROID_MAIN_CONFIG_XML = ROOT / "frontend" / "android" / "app" / "src" / "main" / "res" / "xml" / "config.xml"
ANDROID_DEBUG_MANIFEST = ROOT / "frontend" / "android" / "app" / "src" / "debug" / "AndroidManifest.xml"
IOS_CONFIG_XML = ROOT / "frontend" / "ios" / "App" / "App" / "config.xml"
CAPACITOR_CONFIG = ROOT / "frontend" / "capacitor.config.ts"
PRODUCTION_ORIGINS = {"https://weisilianghua.cloud", "https://www.weisilianghua.cloud"}


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
    errors.extend(_navigation_whitelist_errors())

    if not ANDROID_PUBLIC.exists():
        errors.append("Android bundled assets are missing. Run `cd frontend && npm run build:native && npx cap sync android`.")
    else:
        js_files = list(ANDROID_PUBLIC.rglob("*.js"))
        if not js_files:
            errors.append("Android bundled assets contain no JavaScript files. Run `cd frontend && npm run build:native && npx cap sync android`.")
        else:
            js_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in js_files)
            marker_pattern = re.compile(
                rf"\b[A-Za-z_$][\w$]*\s*=\s*{expected_code}\b"
                r"[\s\S]{0,500}tquant\.dismissed_android_update"
                r"|tquant\.dismissed_android_update[\s\S]{0,500}"
                rf"\b[A-Za-z_$][\w$]*\s*=\s*{expected_code}\b"
            )
            if not marker_pattern.search(js_text):
                errors.append("Native bundled update version marker was not found. Run `cd frontend && npm run build:native && npx cap sync android`.")

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


def _navigation_whitelist_errors() -> list[str]:
    errors: list[str] = []
    if not CAPACITOR_CONFIG.exists():
        errors.append("Capacitor config is missing.")
    else:
        source = CAPACITOR_CONFIG.read_text(encoding="utf-8", errors="ignore")
        production_ip_fragment = ".".join(("43", "143", "243", "97"))
        blocked_fragments = (production_ip_fragment, "http://", "localhost", "127.0.0.1")
        for fragment in blocked_fragments:
            if fragment in source:
                errors.append(f"Capacitor production config must not allow navigation to {fragment}.")
    errors.extend(_config_xml_origin_errors(ANDROID_MAIN_CONFIG_XML, "Android release config.xml"))
    errors.extend(_config_xml_origin_errors(IOS_CONFIG_XML, "iOS release config.xml"))
    duplicate_ios_config = ROOT / "frontend" / "ios" / "App" / "App" / "config 2.xml"
    if duplicate_ios_config.exists():
        errors.append("Duplicate iOS config 2.xml must not be present in release sources.")
    return errors


def _config_xml_origin_errors(path: Path, label: str) -> list[str]:
    if not path.exists():
        return [f"{label} is missing."]
    try:
        root = ElementTree.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    except ElementTree.ParseError as exc:
        return [f"{label} is not valid XML: {exc}"]
    origins = {
        value.strip()
        for node in root.findall("{http://www.w3.org/ns/widgets}access")
        for value in [node.attrib.get("origin", "")]
        if value.strip()
    }
    errors: list[str] = []
    if "*" in origins:
        errors.append(f"{label} must not use wildcard access origin.")
    insecure = sorted(origin for origin in origins if origin.startswith("http://") or "localhost" in origin or "127.0.0.1" in origin)
    if insecure:
        errors.append(f"{label} contains non-production origins: {', '.join(insecure)}")
    unexpected = sorted(origin for origin in origins if origin not in PRODUCTION_ORIGINS)
    if unexpected:
        errors.append(f"{label} contains origins outside production whitelist: {', '.join(unexpected)}")
    missing = sorted(PRODUCTION_ORIGINS - origins)
    if missing:
        errors.append(f"{label} is missing production origins: {', '.join(missing)}")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
