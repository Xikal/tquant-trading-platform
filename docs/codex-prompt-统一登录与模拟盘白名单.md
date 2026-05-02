# Codex 任务：统一登录 + 模拟盘白名单

**目标**：Web 端与 App 端共用 JWT 认证体系；模拟盘功能支持白名单控制，仅白名单用户可访问。

**原则**：不拆分两套认证，不引入新依赖，最小化数据库变更，用户无感知平滑升级。

**总任务数**：11 个任务，按执行顺序分为 4 个阶段。

---

## 当前状态速查

| 维度 | 当前状态 | 问题 |
|------|---------|------|
| App 登录 | JWT（`/api/auth/*`），含 register/login/refresh/logout/me | 完善 |
| Web 登录 | 无用户登录——Settings 用 admin token，其余路由公开 | Web 端无用户身份 |
| 模拟盘登录 | 复用 App JWT，有独立登录面板 | 可用但未控制权限 |
| User 模型 | `users` 表：id, username, display_name, password_hash, is_active, created_at, updated_at | 无角色/权限/白名单字段 |
| 公开路由 | watchlist signals、priority board、analysis、market data | 行情和策略信号确实应该公开 |

---

## 目标架构

```
Web 端                           App 端
   │                               │
   ├─ 登录/注册表单                 ├─ 登录/注册表单
   │      │                         │      │
   │      ▼                         │      ▼
   │  POST /api/auth/login          │  POST /api/auth/login
   │  POST /api/auth/register       │  POST /api/auth/register
   │      │                         │      │
   │      ▼                         │      ▼
   │  JWT access_token (15min)      │  JWT access_token (15min)
   │  refresh_token (httpOnly)      │  refresh_token (httpOnly)
   │      │                         │      │
   │      ▼                         │      ▼
   │  统一用户身份 (User)            │  统一用户身份 (User)
   │      │                         │      │
   │      ├─ 公开 API（无需登录）     │      ├─ 公开 API（无需登录）
   │      │  /api/watchlist/signals  │      │  /api/app/bootstrap
   │      │  /api/screeners/*        │      │  /api/app/low-buy
   │      │  /api/analyze            │      │
   │      │                          │      │
   │      └─ 私有 API（需登录）       │      └─ 私有 API（需登录）
   │         /api/watchlist (自选)    │         /api/app/home
   │         /api/paper/* (模拟盘)    │         /api/app/watchlist
   │              │                  │         /api/app/low-buy/{s}/favorite
   │              ▼                  │
   │         白名单检查               │
   │         can_paper_trade?        │
```

Web 端与 App 端通过同一个 `/api/auth/*` 体系认证，区别仅在于：
- App 端注册时 `device_name: "mobile-app"`
- Web 端注册时 `device_name: "web"`

---

## 阶段一：数据模型与配置（3 个任务）

### 任务 1：User 模型增加白名单字段

**文件**：`backend/app/models/entities.py`，`User` 类（约第 55-66 行）

**当前代码**：
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(220))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

**修改为**：
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(220))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    can_paper_trade: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # 新增：模拟盘白名单
    roles: Mapped[str] = mapped_column(String(256), default="")  # 新增：逗号分隔的角色标签，为未来 RBAC 预留
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

**字段说明**：
- `can_paper_trade`：默认 `False`。需通过 settings 接口或数据库直接设置为 `True` 才能使用模拟盘
- `roles`：逗号分隔字符串，如 `"admin,paper_trader"`。当前只用于 `can_paper_trade` 的批量管理，不参与路由鉴权

**数据库迁移**（自动执行，在 `init_db` 中追加）：
```python
# backend/app/core/database.py 的 init_db 函数中追加：
from sqlalchemy import text

def _migrate_users_add_whitelist():
    """幂等迁移：为 users 表添加白名单字段。"""
    with SessionLocal() as db:
        # 检查列是否存在
        try:
            db.execute(text("SELECT can_paper_trade FROM users LIMIT 1"))
        except Exception:
            db.execute(text("ALTER TABLE users ADD COLUMN can_paper_trade BOOLEAN NOT NULL DEFAULT 0"))
            db.execute(text("ALTER TABLE users ADD COLUMN roles VARCHAR(256) NOT NULL DEFAULT ''"))
            db.commit()
```

在 `init_db` 末尾调用 `_migrate_users_add_whitelist()`。

**验证**：
```bash
sqlite3 data/gupiao.db ".schema users" | grep "can_paper_trade\|roles"
# 应看到两个新字段
```

---

### 任务 2：配置白名单开关

**文件**：`backend/app/core/config.py`，`AppSettings` 类（约第 44-46 行附近）

在现有 auth 配置后追加：
```python
    # 模拟盘白名单控制
    paper_trading_whitelist_enabled: bool = False  # 默认关闭，管理员通过 settings 接口开启
    paper_trading_admin_bypass: bool = True  # 管理员 always 有权限
```

**文件**：`backend/app/models/schema_defs/settings.py`

如果存在 Settings 响应模型，追加：
```python
    paper_trading_whitelist_enabled: bool = False
```

**验证**：
```bash
grep -n "paper_trading_whitelist" backend/app/core/config.py
# 应看到两个新字段
```

---

### 任务 3：创建白名单检查依赖

**新建文件**：`backend/app/core/paper_auth.py`

```python
"""模拟盘白名单鉴权依赖。"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.models.entities import User

logger = logging.getLogger(__name__)


def require_paper_trading(user: User = Depends(get_current_user)) -> User:
    """检查当前用户是否有模拟盘访问权限。

    权限判定逻辑：
    1. 用户 is_active == False → 403
    2. paper_trading_whitelist_enabled == False → 全部放行
    3. paper_trading_whitelist_enabled == True:
       a. 用户 can_paper_trade == True → 放行
       b. 用户 is_active 且 admin_bypass 开启且 roles 含 "admin" → 放行
       c. 其他 → 403
    """
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    settings = get_settings()
    if not settings.paper_trading_whitelist_enabled:
        return user

    if user.can_paper_trade:
        return user

    # 管理员绕过
    if settings.paper_trading_admin_bypass:
        roles = [r.strip() for r in (user.roles or "").split(",") if r.strip()]
        if "admin" in roles:
            return user

    logger.info("Paper trading access denied for user %s (id=%s)", user.username, user.id)
    raise HTTPException(
        status_code=403,
        detail="模拟盘功能需要申请白名单权限。请联系管理员开通。",
    )


def get_user_can_paper_trade(user: User = Depends(get_current_user)) -> bool:
    """返回用户是否可以访问模拟盘（不抛异常，用于前端判断）。"""
    if not user.is_active:
        return False
    settings = get_settings()
    if not settings.paper_trading_whitelist_enabled:
        return True
    if user.can_paper_trade:
        return True
    if settings.paper_trading_admin_bypass:
        roles = [r.strip() for r in (user.roles or "").split(",") if r.strip()]
        if "admin" in roles:
            return True
    return False
```

**验证**：
```bash
python -c "from app.core.paper_auth import require_paper_trading; print('import OK')"
```

---

## 阶段二：后端路由改造（3 个任务）

### 任务 4：模拟盘路由接入白名单检查

**文件**：`backend/app/api/routes/paper.py`

**当前代码**：所有模拟盘路由使用 `Depends(get_current_user)`

**改为**：所有模拟盘路由使用 `Depends(require_paper_trading)`

**修改方式** —— 在文件顶部 import：
```python
from app.core.paper_auth import require_paper_trading, get_user_can_paper_trade
```

然后将所有 `current_user: User = Depends(get_current_user)` 替换为 `current_user: User = Depends(require_paper_trading)`。

全部替换点（共约 17 处）：
- 第 39 行：`GET /paper/account`
- 第 50 行：`POST /paper/account`
- 第 62 行：`POST /paper/account/reset`
- 第 69 行：`POST /paper/account/pause`
- 第 76 行：`POST /paper/account/resume`
- 第 84 行：`GET /paper/positions`
- 第 100 行：`GET /paper/positions/{symbol}`
- 第 112 行：`POST /paper/positions/refresh`
- 第 129 行：`GET /paper/risk`
- 第 142 行：`GET /paper/orders`
- 第 152 行：`POST /paper/orders`
- 第 185 行：`GET /paper/orders/{order_id}`
- 第 201 行：`POST /paper/orders/{order_id}/cancel`
- 第 218 行：`GET /paper/trades`
- 第 232 行：`GET /paper/performance`
- 第 240 行：`GET /paper/performance/by-strategy`
- 第 249 行：`GET /paper/performance/by-market-state`

**在文件末尾追加一个新路由**，用于前端判断用户是否有模拟盘权限：
```python
@router.get("/paper/access")
def check_paper_access(current_user: User = Depends(get_current_user)) -> dict:
    """检查当前用户是否有模拟盘访问权限（不抛 403，返回布尔值）。"""
    can_access = get_user_can_paper_trade(current_user)
    return {
        "can_access": can_access,
        "whitelist_enabled": get_settings().paper_trading_whitelist_enabled,
        "user_can_paper_trade": current_user.can_paper_trade,
    }
```

**验证**：
```bash
grep -c "require_paper_trading" backend/app/api/routes/paper.py
# 应 >= 17（每个受保护路由一个）
grep -n "paper/access" backend/app/api/routes/paper.py
# 应看到新路由
```

---

### 任务 5：auth/me 接口返回白名单信息

**文件**：`backend/app/api/routes/auth.py`，`GET /auth/me` 路由（约第 92-94 行）

在 `AuthMeResponse` 中增加 `can_paper_trade` 和 `roles` 字段。

**修改 schema**：`backend/app/models/schema_defs/auth.py`

在 `AuthMeResponse` 和 `AuthUserOut` 中追加：
```python
class AuthUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    can_paper_trade: bool = False   # 新增
    roles: str = ""                  # 新增
    created_at: datetime

class AuthMeResponse(BaseModel):
    user: AuthUserOut
    can_paper_trade: bool = False    # 新增：冗余字段，方便前端直接判断
```

**修改 auth.py 路由函数**（第 92-94 行）：
```python
@router.get("/me", response_model=AuthMeResponse)
def get_me(current_user: User = Depends(get_current_user)) -> dict:
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "display_name": current_user.display_name,
            "can_paper_trade": current_user.can_paper_trade,
            "roles": current_user.roles,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "can_paper_trade": current_user.can_paper_trade,
    }
```

**验证**：
```bash
# 登录后调用：
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/auth/me
# 应包含 can_paper_trade 字段
```

---

### 任务 6：用户管理 API（管理员设置白名单）

**新建文件**：`backend/app/api/routes/admin_users.py`

```python
"""用户管理 API —— 管理员设置白名单和角色。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.admin_auth import require_admin_auth
from app.core.database import get_db
from app.models.entities import User

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class UpdateUserRequest(BaseModel):
    can_paper_trade: bool | None = Field(None, description="设为 True 加入模拟盘白名单")
    roles: str | None = Field(None, max_length=256, description="逗号分隔角色，如 admin,paper_trader")
    is_active: bool | None = Field(None)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_active: bool
    can_paper_trade: bool
    roles: str
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[UserOut])
def list_users(
    can_paper_trade: bool | None = None,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_auth),
):
    """列出所有用户，可按白名单状态筛选。"""
    from sqlalchemy import select

    stmt = select(User).order_by(User.id)
    if can_paper_trade is not None:
        stmt = stmt.where(User.can_paper_trade == can_paper_trade)
    return [UserOut.model_validate(u) for u in db.execute(stmt).scalars().all()]


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin_auth),
):
    """更新用户白名单状态、角色、激活状态。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.can_paper_trade is not None:
        user.can_paper_trade = body.can_paper_trade
    if body.roles is not None:
        user.roles = body.roles
    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/whitelist", response_model=list[UserOut])
def list_whitelisted(db: Session = Depends(get_db), _admin=Depends(require_admin_auth)):
    """列出所有模拟盘白名单用户。"""
    from sqlalchemy import select

    stmt = select(User).where(User.can_paper_trade == True).order_by(User.id)
    return [UserOut.model_validate(u) for u in db.execute(stmt).scalars().all()]
```

**注册路由**：在 `backend/app/api/router.py` 中追加：
```python
from app.api.routes.admin_users import router as admin_users_router
# ...
api_router.include_router(admin_users_router)
```

**验证**：
```bash
# 需要 admin token
curl -H "X-Admin-Token: <token>" http://localhost:8000/api/admin/users
curl -X PUT -H "X-Admin-Token: <token>" -H "Content-Type: application/json" \
  -d '{"can_paper_trade": true}' http://localhost:8000/api/admin/users/1
```

---

## 阶段三：Web 端统一登录（3 个任务）

### 任务 7：Web 端全局认证状态管理

**新建文件**：`frontend/src/features/trading-workspace/useAuth.ts`

```typescript
import { useState, useCallback, useEffect } from "react";
import { appApi } from "../../api/appClient";
import { getAuthAccessToken, setAuthTokens, clearAuthTokens } from "../../api/base";

export interface AuthState {
  isLoggedIn: boolean;
  username: string;
  displayName: string;
  canPaperTrade: boolean;
  loading: boolean;
}

export function useAuth() {
  const [auth, setAuth] = useState<AuthState>({
    isLoggedIn: false,
    username: "",
    displayName: "",
    canPaperTrade: false,
    loading: true,
  });

  // 页面加载时恢复会话
  const restoreSession = useCallback(async () => {
    if (!getAuthAccessToken()) {
      // 尝试 cookie refresh
      try {
        await appApi.refreshAuth();
      } catch {
        setAuth(prev => ({ ...prev, loading: false }));
        return;
      }
    }
    try {
      const me = await appApi.getMe();
      setAuth({
        isLoggedIn: true,
        username: me.user.username,
        displayName: me.user.display_name,
        canPaperTrade: me.user.can_paper_trade,
        loading: false,
      });
    } catch {
      clearAuthTokens();
      setAuth(prev => ({ ...prev, loading: false }));
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const login = useCallback(async (username: string, password: string) => {
    const result = await appApi.login({ username, password, device_name: "web" });
    setAuthTokens(result.access_token);
    const me = await appApi.getMe();
    setAuth({
      isLoggedIn: true,
      username: me.user.username,
      displayName: me.user.display_name,
      canPaperTrade: me.user.can_paper_trade,
      loading: false,
    });
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    const result = await appApi.register({ username, password, display_name: username, device_name: "web" });
    setAuthTokens(result.access_token);
    const me = await appApi.getMe();
    setAuth({
      isLoggedIn: true,
      username: me.user.username,
      displayName: me.user.display_name,
      canPaperTrade: me.user.can_paper_trade,
      loading: false,
    });
  }, []);

  const logout = useCallback(async () => {
    try { await appApi.logout(); } catch { /* ignore */ }
    clearAuthTokens();
    setAuth({
      isLoggedIn: false,
      username: "",
      displayName: "",
      canPaperTrade: false,
      loading: false,
    });
  }, []);

  return { auth, login, register, logout, restoreSession };
}
```

**验证**：
```bash
grep -n "useAuth" frontend/src/features/trading-workspace/useAuth.ts
```

---

### 任务 8：Web 端顶栏登录入口

**文件**：`frontend/src/features/trading-workspace/TradingWorkspace.tsx`

**在 Topbar 组件的右上角操作区增加登录状态显示**。

找到 Topbar 的渲染位置（约第 480-500 行），在 actions 区追加登录/用户入口。

**在 TradingWorkspace 中引入 useAuth**：
```tsx
import { useAuth } from "./useAuth";

// 在组件内部：
const { auth, login, register, logout } = useAuth();
const [showAuthModal, setShowAuthModal] = useState(false);
```

**在 Topbar 的 desk chips 区域（右侧状态区）增加**：
```tsx
{auth.loading ? (
  <span className="desk-chip muted">验证中...</span>
) : auth.isLoggedIn ? (
  <span className="desk-chip" onClick={() => setShowAuthModal(false)} style={{ cursor: "pointer" }}>
    {auth.displayName || auth.username}
    {auth.canPaperTrade && <span className="hint gold">·模拟盘</span>}
    <button className="inline-button" onClick={(e) => { e.stopPropagation(); logout(); }}>退出</button>
  </span>
) : (
  <button className="ghost-button" onClick={() => setShowAuthModal(true)}>登录</button>
)}
```

**新建登录弹窗组件**（可复用 PaperTradingPage 中的登录表单）：

**新建文件**：`frontend/src/features/trading-workspace/LoginModal.tsx`

```tsx
import { useState } from "react";

interface LoginModalProps {
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onClose: () => void;
  error?: string;
  loading: boolean;
}

export function LoginModal({ onLogin, onRegister, onClose, error, loading }: LoginModalProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");

  const handleSubmit = async () => {
    if (mode === "login") {
      await onLogin(username, password);
    } else {
      await onRegister(username, password);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="panel-title">
          <span className="hint">AUTH</span>
          <h2>{mode === "login" ? "登录" : "注册"}</h2>
          <button className="inline-button" onClick={onClose}>✕</button>
        </div>
        <p className="muted">登录后可使用模拟盘和个人自选股功能。</p>
        <div className="form-grid">
          <label>
            <span>账号</span>
            <input value={username} autoComplete="username" onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label>
            <span>密码</span>
            <input value={password} type="password" autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} />
          </label>
        </div>
        {error && <div className="warn">{error}</div>}
        <div className="actions">
          <button className="primary-button" onClick={handleSubmit} disabled={loading}>
            {mode === "login" ? "登录" : "注册"}
          </button>
          <button className="ghost-button" onClick={() => setMode(mode === "login" ? "register" : "login")}>
            {mode === "login" ? "没有账号？注册" : "已有账号？登录"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**在 TradingWorkspace 中渲染 LoginModal**：
```tsx
{showAuthModal && (
  <LoginModal
    onLogin={login}
    onRegister={register}
    onClose={() => setShowAuthModal(false)}
    error={error}
    loading={loading === "auth"}
  />
)}
```

**验证**：前端构建通过 + 手动测试登录/注册流程。

---

### 任务 9：Web 端自选股路由增加鉴权

Web 端的 watchlist 路由（增删改）当前不要求登录。应改为要求登录。

**文件**：`backend/app/api/routes/watchlist.py`

找到 `POST /watchlist` 和 `DELETE /watchlist/{symbol}` 路由，添加 `Depends(get_current_user)`：

```python
from app.core.auth import get_current_user

@router.post("/watchlist")
def upsert_watchlist(
    body: WatchlistUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 新增
):
    # ... 现有逻辑 ...

@router.delete("/watchlist/{symbol}")
def delete_watchlist(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 新增
):
    # ... 现有逻辑 ...
```

`GET /watchlist` 和 `GET /watchlist/signals` 保持公开（信号数据全局共享）。

**验证**：
```bash
# 未登录时 POST/DELETE 应返回 401
curl -X POST http://localhost:8000/api/watchlist -d '{"symbol":"510300"}' -H "Content-Type: application/json"
```

---

## 阶段四：整合与验证（2 个任务）

### 任务 10：前端的 TypeScript 类型同步

**文件**：`frontend/src/types/auth.ts`（新建）

```typescript
export interface AuthUser {
  id: number;
  username: string;
  display_name: string;
  can_paper_trade: boolean;
  roles: string;
  created_at: string;
}

export interface AuthMeResponse {
  user: AuthUser;
  can_paper_trade: boolean;
}

export interface PaperAccessResponse {
  can_access: boolean;
  whitelist_enabled: boolean;
  user_can_paper_trade: boolean;
}
```

**更新 `frontend/src/api/appClient.ts`** 中 `getMe()` 的返回类型：
```typescript
async getMe(): Promise<AuthMeResponse> {
    return request<AuthMeResponse>("/auth/me", { credentials: "include" });
}
```

**更新 PaperTradingPage**：当用户登录但无白名单权限时显示友好提示而非直接隐藏。

**验证**：
```bash
npx tsc --noEmit  # 前端类型检查通过
```

---

### 任务 11：集成测试与验收

**新建文件**：`backend/tests/test_paper_whitelist.py`

```python
"""模拟盘白名单集成测试。"""
import unittest

from app.core.config import get_settings
from app.core.paper_auth import require_paper_trading, get_user_can_paper_trade


class PaperWhitelistTest(unittest.TestCase):

    def test_01_import_works(self):
        """验证白名单模块可正常导入。"""
        from app.core.paper_auth import require_paper_trading
        self.assertTrue(callable(require_paper_trading))

    def test_02_config_defaults(self):
        """验证白名单配置默认值。"""
        settings = get_settings()
        self.assertFalse(settings.paper_trading_whitelist_enabled,
                         "默认应关闭白名单，避免影响现有用户")
        self.assertTrue(settings.paper_trading_admin_bypass,
                        "管理员默认应有绕过权限")

    def test_03_user_model_has_fields(self):
        """验证 User 模型包含白名单字段。"""
        from app.models.entities import User
        self.assertTrue(hasattr(User, 'can_paper_trade'))
        self.assertTrue(hasattr(User, 'roles'))

    def test_04_admin_users_api_exists(self):
        """验证管理员用户管理 API 可导入。"""
        from app.api.routes.admin_users import router
        self.assertTrue(hasattr(router, 'routes'))

    def test_05_paper_access_endpoint(self):
        """验证 /api/paper/access 路由存在。"""
        from app.api.routes.paper import router
        paths = [r.path for r in router.routes]
        self.assertIn("/paper/access", paths)
```

**冒烟测试**（需要服务运行）：
```bash
# 1. 注册新用户（默认无白名单）
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test_trader","password":"test123456","device_name":"web"}'

# 2. 尝试访问模拟盘（应 403）
TOKEN=<从上面获取的 access_token>
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/paper/account
# 应返回 403

# 3. 管理员加白名单
curl -X PUT -H "X-Admin-Token: <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"can_paper_trade": true}' \
  http://localhost:8000/api/admin/users/1

# 4. 再次访问模拟盘（应 200）
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/paper/account

# 5. 检查 paper/access
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/paper/access
# 应返回 {"can_access": true, ...}
```

**验收标准**：

| 检查项 | 通过标准 |
|--------|---------|
| User 模型迁移 | `can_paper_trade` 和 `roles` 字段存在，默认值正确 |
| 白名单关闭时 | 所有已登录用户可正常访问模拟盘 |
| 白名单开启时 | 仅 `can_paper_trade=True` 的用户可访问模拟盘 |
| 白名单开启时，非白名单用户 | 返回 403 + 中文提示 "模拟盘功能需要申请白名单权限" |
| 管理员绕过 | `roles="admin"` 的用户在白名单开启时仍可访问 |
| Web 端登录 | 顶栏显示登录入口，登录后可看到用户名 |
| Web 端未登录 | 公开路由（行情/信号/筛选）仍可正常访问 |
| App 端不受影响 | App 端登录/注册/自选/监控功能正常 |
| 用户管理 API | 管理员可通过 API 列出用户、设置白名单 |
| paper/access 端点 | 返回当前用户的模拟盘权限状态 |

---

## 任务依赖关系

```
任务 1 (User 模型)  ──→  任务 2 (配置)  ──→  任务 3 (白名单依赖)
                                              │
                    ┌─────────────────────────┘
                    ▼
              任务 4 (paper 路由)
              任务 5 (auth/me)
              任务 6 (admin API)
                    │
                    ▼
              任务 7 (useAuth hook)
                    │
                    ▼
              任务 8 (顶栏登录)
              任务 9 (watchlist 鉴权)
                    │
                    ▼
              任务 10 (类型同步)
                    │
                    ▼
              任务 11 (集成测试)
```

任务 4-6 可并行执行；任务 8-9 可并行执行。

---

## 被排除的设计决策

以下决策经评估后不采用：

| 方案 | 理由 |
|------|------|
| OAuth2 / 第三方登录（微信/Google） | V1 阶段不需要，用户名+密码足够 |
| RBAC 完整角色系统 | 过度设计。当前仅需 `can_paper_trade` 布尔 + `roles` 字符串预留 |
| 独立的白名单表 | 过度设计。单布尔字段在 1000 用户以下完全够用 |
| App 端独立认证体系 | 已有 JWT 体系，Web 端直接复用 |
| 所有 Web 路由强制登录 | 行情/信号/筛选等数据全局共享，不应强制登录 |
| 接入第三方 auth 库 (authlib/oauthlib) | 当前自定义 HMAC 实现足够，换库不带来收益 |

---

*本方案所有改动仅涉及鉴权和白名单控制，不修改任何策略逻辑、信号生成、因子计算或业务规则。*
