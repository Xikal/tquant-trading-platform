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
  const [verifying, setVerifying] = useState(false)
  const [updateError, setUpdateError] = useState("")

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
      setUpdateError("")
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
    setUpdateError("")
  }, [updateInfo])

  const openUpdate = useCallback(async () => {
    if (!updateInfo?.apk_url) {
      return
    }
    try {
      setVerifying(true)
      setUpdateError("")
      await verifyApkChecksum(updateInfo.apk_url, updateInfo.apk_sha256)
      await Browser.open({ url: updateInfo.apk_url })
    } catch (err) {
      setUpdateError(err instanceof Error ? err.message : "安装包校验失败，请稍后重试。")
    } finally {
      setVerifying(false)
    }
  }, [updateInfo])

  useEffect(() => {
    void checkForUpdate()
  }, [])

  return {
    updateInfo,
    updateError,
    checkForUpdate,
    dismissUpdate,
    openUpdate,
    verifying
  }
}

async function verifyApkChecksum(apkUrl: string, expectedSha256: string) {
  const expected = expectedSha256.trim().toLowerCase()
  if (!expected) {
    throw new Error("安装包缺少 SHA256 校验值，已阻止更新。")
  }
  if (!globalThis.crypto?.subtle) {
    throw new Error("当前设备不支持安装包校验，已阻止更新。")
  }
  const response = await fetch(apkUrl, {
    cache: "no-store",
    credentials: "include"
  })
  if (!response.ok) {
    throw new Error(`安装包下载失败: ${response.status}`)
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", await response.arrayBuffer())
  const actual = Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")
  if (actual !== expected) {
    throw new Error("安装包 SHA256 校验不一致，已阻止更新。")
  }
}
