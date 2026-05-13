import { useEffect, useState } from "react"
import { clearAuthTokens, getAuthAccessToken } from "../api/base"
import { appApi } from "../api/appClient"
import type { AuthUser } from "../types"

export interface MobileAuthSubmitPayload {
  username: string
  password: string
  mfa_code?: string
  register: boolean
}

export function useMobileAuth() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState("")

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
  }, [])

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
            mfa_code: payload.mfa_code,
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
