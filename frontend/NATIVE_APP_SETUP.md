# 原生 App 开发与联调

当前原生 App 使用 `Capacitor` 包裹现有 React 前端，只保留两条链路：

- 实时监控
- 选股宝典

Web 工作台中的 `量化分析 / 研究复盘 / 系统配置` 不会进入 native build。

## 1. 准备后端地址

原生 App 不能直接使用默认的 `/api` 相对地址。  
native build 必须显式配置：

```bash
cp .env.native.example .env.native.local
```

然后把 `VITE_API_BASE_URL` 改成真实后端的 `/api` 前缀，例如：

```bash
VITE_APP_TARGET=native
VITE_API_BASE_URL=https://your-backend.example.com/api
```

本地真机联调时，如果后端没有公网地址，可以直接使用项目根目录现成脚本：

```bash
cd /Users/j/Documents/gupiao
./scripts/run_public_app.sh
```

脚本会把公网地址写到：

- `.runtime/public_url.txt`

把这个地址拼成：

```text
https://<public-host>/api
```

再填回 `frontend/.env.native.local`。

## 2. Native 构建

安装依赖后执行：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run build:native
```

输出目录：

- `frontend/dist-native`

原生入口：

- `frontend/src/main-native.tsx`

## 3. 同步 Capacitor 平台工程

```bash
cd /Users/j/Documents/gupiao/frontend
npm run cap:sync
```

这会完成：

- native build
- 同步 web 资源到 iOS / Android
- 同步官方 Capacitor 插件

当前平台目录：

- `frontend/ios`
- `frontend/android`

## 4. iOS 开发

打开工程：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run cap:ios
```

要求：

- 已安装完整 Xcode
- `xcodebuild` 可用

当前这台机器只有 `CommandLineTools`，没有完整 Xcode，所以还不能直接编译 iOS。

## 5. Android 开发

打开工程：

```bash
cd /Users/j/Documents/gupiao/frontend
npm run cap:android
```

要求：

- 已安装 Java Runtime
- 已安装 Android Studio / Android SDK
- 已配置 `ANDROID_HOME` 或 `ANDROID_SDK_ROOT`

当前这台机器没有 Java 和 Android SDK，所以还不能直接编译 Android。

## 6. 当前 native 架构

原生入口和 Web 入口已经拆开：

- Web：`frontend/src/main.tsx`
- Native：`frontend/src/main-native.tsx`

native 运行页：

- `frontend/src/mobile/MobileApp.tsx`

公共数据层：

- `frontend/src/features/app-preview/hooks.ts`
- `frontend/src/features/app-preview/lowBuyAdapter.ts`

关键约束：

- 实时监控仍走 `/api/app/home`
- 选股宝典直接复用 Web 端 `/api/screeners/low-buy?scan_mode=full`
- native build 不再打包桌面工作台页面

## 7. 推荐下一步

1. 安装完整 Xcode，完成 iOS simulator 编译
2. 安装 Java 和 Android SDK，完成 Android debug 编译
3. 接入 App 图标、启动图和应用名细节
4. 给 native 加设备级异常上报和网络失败页
