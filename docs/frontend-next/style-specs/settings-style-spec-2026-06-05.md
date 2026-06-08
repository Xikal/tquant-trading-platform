# Settings Web Style Spec - 2026-06-05

## Binding Image

- Web style image: `docs/frontend-next/style-specs/images/settings-web.png`
- Current route: `/settings`
- New `frontend-next` route: `/settings`
- Approved Web viewport: `1440x900`

## Source Anchors

- Plan: `docs/frontend-next-solid-parallel-development-plan-2026-06-05.md`
- Tokens/CSS: `frontend/src/styles/foundation/tokens.css`, `frontend/src/features/settings/SettingsLayout.module.css`
- Page/component sources: `frontend/src/features/settings/SettingsPage.tsx`, `SettingsLayout.tsx`, `SettingsSection.tsx`, `SettingsPagePanels.tsx`, `AuthSecurityCard.tsx`, `FactorWeightSettingsCard.tsx`, `LatestDataStatusCard.tsx`, `DataCenterEntryCard.tsx`, `AdminTokenGate.tsx`

## Visible Section Order

1. Fixed sidebar and sticky topbar.
2. Sticky settings top bar with title "系统设置", summary, unsaved pill when needed, "刷新配置", "全部保存".
3. Settings body grid with side navigation on the left and content on the right.
4. Side nav tabs: "账户与安全", "交易偏好", admin group, "模型与因子", "数据与运行", "诊断与审计".
5. Active section header with title/description/admin badge if applicable.
6. Section cards, such as auth/security, ritual settings, risk parameters, sector filter, admin token gate, runtime snapshots, governance, feature flags, audit.

## Density Rules

- `.settings-layout` gap `--sp-4`.
- Top bar is sticky, 1px border, 10px radius, `--sp-3` padding, subtle backdrop blur.
- Body desktop columns `minmax(180px, 220px) minmax(0, 880px)`, centered.
- Side nav is sticky, gap `--sp-2`, padding `--sp-2`, nav buttons min-height 46px.
- Section cards use `--sp-3` gaps; form grids use two columns and `--sp-3`.

## Color Token Mapping

- Topbar/sidebar nav cards use standard light workspace tokens.
- Active nav item uses `--brand-soft` and border mixed with `--brand`.
- Unsaved/admin gate states use `--warning`; ready state uses `--success`.
- Text hierarchy uses `--text-1`, `--text-2`, `--text-3`.

## Typography And Spacing

- Topbar title `--fs-md`, 700; summary `--fs-micro`.
- Nav labels `--fs-sm`, 700; descriptions `--fs-micro`.
- Section title `--fs-md`, 700; description `--fs-micro`.
- Form field labels and hints follow current shared form components; no large headings.

## Component Inventory

- `SettingsLayout`
- `SettingsNavItem`
- `SettingsSection`
- `AuthSecurityCard`
- `RitualSettingsCard`
- `SettingCard`
- `SectorFilterCard`
- `QuantParameterPaperExitCard`
- `QuantParameterSectorEtfCard`
- `QuantParameterMlCard`
- `FactorWeightSettingsCard`
- `DataCenterEntryCard`
- `RuntimeSnapshotPanel`
- `FeatureFlagsCard`
- `OperationAuditCard`
- `AdminTokenGate`

## Web Layout Behavior

- Settings top bar and side nav are sticky on desktop.
- Side nav becomes horizontal only below 900px; Web reference is desktop.
- Unsaved pill appears only when `unsavedCount > 0` and must not shift primary actions off-screen.
- Admin sections render only for admins; non-admins see account/trading tabs only.
- Save buttons remain explicit; no autosave styling or hidden state changes.

## Visual Non-Goals

- Do not create a new settings IA or split this into separate pages.
- Do not move data-maintenance workflows back from `/data` into settings.
- Do not show secret values; preserve configured/unconfigured state wording.
- Do not add colorful preference widgets beyond existing token states.

## Screenshot Parity Checklist

- [ ] `1440x900` screenshot shows sticky settings top bar, side nav, and active content cards.
- [ ] Side nav width, button height, and active brand-soft state match current CSS.
- [ ] Section cards and form grid use current 2-column desktop density.
- [ ] Admin token and unsaved states use warning/success tokens only.
- [ ] No horizontal overflow or redesigned settings theme appears.
