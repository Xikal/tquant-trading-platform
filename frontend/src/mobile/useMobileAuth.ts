import { useEffect } from "react"
import { clearAuthTokens, getAuthAccessToken } from "../api/base"
import { appApi } from "../api/appClient"
import type { AuthUser } from "../types"
import { useMobileUiStore } from "../stores/mobileUiStore"
import { useServerState } from "../state/serverState"

export interface MobileAuthSubmitPayload {
  username: string
  password: string
  register: boolean
}

const MOBILE_AUTH_USER_KEY = ["mobile", "auth-user"] as const;

export function useMobileAuth() {
  const [authUser, setAuthUser] = useServerState<AuthUser | null>(MOBILE_AUTH_USER_KEY, null)
  const authLoading = useMobileUiStore((state) => state.authLoading)
  const authError = useMobileUiStore((state) => state.authError)
  const setAuthLoading = useMobileUiStore((state) => state.setAuthLoading)
  const setAuthError = useMobileUiStore((state) => state.setAuthError)

  useEffect(() => {
    const restoreAuth = async () => {
      try {
        if (getAuthAccessToken()) {
          const payload = await appApi.getMe()
          setAuthUser(payload.user)
          setAuthError("")
          return
        }
        const refreshed = await appApi.refreshAuth()
        setAuthUser(refreshed.user)
        setAuthError("")
      } catch (err) {
        clearAuthTokens()
        setAuthUser(null)
        setAuthError(getAuthAccessToken() ? (err instanceof Error ? err.message : "登录已失效") : "")
      } finally {
        setAuthLoading(false)
      }
    }
    void restoreAuth()
  }, [setAuthError, setAuthLoading, setAuthUser])

  async function handleAuthSubmit(payload: MobileAuthSubmitPayload) {
    try {
      setAuthLoading(true)
      setAuthError("")
      const result = payload.register
        ? await appApi.register({
            username: payload.username,
            password: payload.password,
            display_name: payload.username,
            device_name: "mobile-app"
          })
        : await appApi.login({
            username: payload.username,
            password: payload.password,
            device_name: "mobile-app"
          })
      setAuthUser(result.user)
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : "登录失败")
    } finally {
      setAuthLoading(false)
    }
  }

  async function handleLogout() {
    await appApi.logout()
    setAuthUser(null)
    setAuthError("")
  }

  return {
    authUser,
    authLoading,
    authError,
    handleAuthSubmit,
    handleLogout
  }
}
