export interface AuthUser {
  id: number
  username: string
  display_name: string
  can_paper_trade: boolean
  roles: string[]
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

export interface PaperAccessResponse {
  can_paper_trade: boolean
  reason: string
}
