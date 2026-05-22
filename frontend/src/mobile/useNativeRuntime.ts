import { App as CapacitorApp, type AppState } from "@capacitor/app"
import { Capacitor } from "@capacitor/core"
import { Network, type ConnectionStatus } from "@capacitor/network"
import { StatusBar, Style } from "@capacitor/status-bar"
import { useEffect } from "react"
import { useMobileUiStore } from "../stores/mobileUiStore"

const isNativeApp = Capacitor.isNativePlatform()

export function useNativeRuntime(onResume?: () => void) {
  const offline = useMobileUiStore((state) => state.offline)
  const setOffline = useMobileUiStore((state) => state.setOffline)

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
        setOffline(!status.connected)
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
      setOffline(!status.connected)
    }).then((listener) => {
      networkListener = listener
    })

    return () => {
      void activeListener?.remove()
      void networkListener?.remove()
    }
  }, [onResume, setOffline])

  return {
    isNativeApp,
    isOnline: !offline
  }
}
