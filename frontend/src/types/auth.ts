export interface AuthUser {
  id: number
  username: string
  display_name: string
  can_paper_trade: boolean
  roles: string[]
  mfa_totp_enabled?: boolean
  created_at: string
}

export interface AuthTokenResponse {
  access_token: string
  refresh_token: string
  token_type: "bearer"
  expires_in: number
  user: AuthUser
}

export interface AuthMeResponse {
  user: AuthUser
}

export interface AuthMfaSetupResponse {
  secret: string
  otpauth_uri: string
  issuer: string
  account_name: string
}

export interface PaperAccessResponse {
  can_paper_trade: boolean
  reason: string
}
