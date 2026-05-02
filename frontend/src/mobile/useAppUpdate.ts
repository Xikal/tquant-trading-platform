import { Browser } from "@capacitor/browser"
import { Capacitor } from "@capacitor/core"
import { useCallback, useEffect, useState } from "react"
import { appApi } from "../api/appClient"
import type { AppAndroidUpdateResponse } from "../types"

const CURRENT_ANDROID_VERSION_CODE = Number(import.meta.env.VITE_NATIVE_VERSION_CODE ?? "1")
const DISMISSED_UPDATE_KEY = "tquant.dismissed_android_update"

function isAndroidNativeApp() {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android"
}

function dismissedVersion() {
  if (typeof window === "undefined") {
    return ""
  }
  return window.localStorage.getItem(DISMISSED_UPDATE_KEY) ?? ""
}

function rememberDismissedVersion(versionCode: number) {
  if (typeof window === "undefined") {
    return
  }
  window.localStorage.setItem(DISMISSED_UPDATE_KEY, String(versionCode))
}

export function useAppUpdate() {
  const [updateInfo, setUpdateInfo] = useState<AppAndroidUpdateResponse | null>(null)
  const [checking, setChecking] = useState(false)

  const checkForUpdate = useCallback(async () => {
    if (!isAndroidNativeApp() || checking) {
      return
    }
    try {
      setChecking(true)
      const payload = await appApi.checkAndroidUpdate(CURRENT_ANDROID_VERSION_CODE)
      const dismissed = dismissedVersion()
      const shouldShow =
        payload.update_available &&
        (payload.mandatory || dismissed !== String(payload.latest_version_code))
      setUpdateInfo(shouldShow ? payload : null)
    } catch {
      // 更新检查不能影响交易主流程。
    } finally {
      setChecking(false)
    }
  }, [checking])

  const dismissUpdate = useCallback(() => {
    if (updateInfo && !updateInfo.mandatory) {
      rememberDismissedVersion(updateInfo.latest_version_code)
    }
    setUpdateInfo(null)
  }, [updateInfo])

  const openUpdate = useCallback(async () => {
    if (!updateInfo?.apk_url) {
      return
    }
    await Browser.open({ url: updateInfo.apk_url })
  }, [updateInfo])

  useEffect(() => {
    void checkForUpdate()
  }, [])

  return {
    updateInfo,
    checkForUpdate,
    dismissUpdate,
    openUpdate
  }
}
