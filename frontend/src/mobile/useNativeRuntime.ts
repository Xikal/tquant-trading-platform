import { App as CapacitorApp, type AppState } from "@capacitor/app"
import { Capacitor } from "@capacitor/core"
import { Network, type ConnectionStatus } from "@capacitor/network"
import { StatusBar, Style } from "@capacitor/status-bar"
import { useEffect, useState } from "react"

export function useNativeRuntime(onResume?: () => void) {
  const [isNativeApp] = useState(() => Capacitor.isNativePlatform())
  const [isOnline, setIsOnline] = useState(true)

  useEffect(() => {
    if (!isNativeApp) {
      return
    }

    let activeListener: { remove: () => Promise<void> } | null = null
    let networkListener: { remove: () => Promise<void> } | null = null

    void StatusBar.setStyle({ style: Style.Dark }).catch(() => undefined)
    void StatusBar.setOverlaysWebView({ overlay: false }).catch(() => undefined)

    void Network.getStatus()
      .then((status) => {
        setIsOnline(status.connected)
      })
      .catch(() => undefined)

    void CapacitorApp.addListener("appStateChange", (state: AppState) => {
      if (state.isActive) {
        onResume?.()
      }
    }).then((listener) => {
      activeListener = listener
    })

    void Network.addListener("networkStatusChange", (status: ConnectionStatus) => {
      setIsOnline(status.connected)
    }).then((listener) => {
      networkListener = listener
    })

    return () => {
      void activeListener?.remove()
      void networkListener?.remove()
    }
  }, [isNativeApp, onResume])

  return {
    isNativeApp,
    isOnline
  }
}
