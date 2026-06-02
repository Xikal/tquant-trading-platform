import { Browser } from "@capacitor/browser";
import { Capacitor } from "@capacitor/core";
import { useCallback, useEffect, useRef } from "react";
import { appApi } from "../api/appClient";

const CURRENT_ANDROID_VERSION_CODE = Number(import.meta.env.VITE_NATIVE_VERSION_CODE ?? "1");
const DISMISSED_UPDATE_KEY = "tquant.dismissed_android_update";

function isAndroidNativeApp() {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android";
}

function readDismissedVersion() {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(DISMISSED_UPDATE_KEY) ?? "";
}

function rememberDismissedVersion(versionCode: number) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(DISMISSED_UPDATE_KEY, String(versionCode));
}

export function useNativeAppUpdate() {
  const checkingRef = useRef(false);

  const checkForUpdate = useCallback(async () => {
    if (!isAndroidNativeApp() || checkingRef.current) {
      return;
    }
    checkingRef.current = true;
    try {
      const payload = await appApi.checkAndroidUpdate(CURRENT_ANDROID_VERSION_CODE);
      if (!payload.update_available) {
        return;
      }
      if (!payload.mandatory && readDismissedVersion() === String(payload.latest_version_code)) {
        return;
      }
      const message = [
        payload.message,
        ...payload.changelog.slice(0, 3),
      ].filter(Boolean).join("\n");
      const shouldOpen = window.confirm(`${payload.title}\n\n${message || "发现新版本，是否下载更新？"}`);
      if (shouldOpen) {
        await Browser.open({ url: payload.apk_url });
      } else if (!payload.mandatory) {
        rememberDismissedVersion(payload.latest_version_code);
      }
    } catch {
      // Native update checks must not block the trading workspace.
    } finally {
      checkingRef.current = false;
    }
  }, []);

  useEffect(() => {
    void checkForUpdate();
  }, [checkForUpdate]);
}
