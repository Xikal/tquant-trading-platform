import { Button, Menu } from "antd";
import { MenuFoldOutlined, MenuUnfoldOutlined } from "../../ui/icons";
import type { AuthUser } from "../../types";
import type { Page } from "../workspace-shared/workspaceTypes";
import { SETTINGS_NAV, visiblePrimaryNav } from "./navConfig";
import {
  SIDEBAR_COLLAPSE_BTN_STYLE,
  SIDEBAR_FOOTER_STYLE,
  SIDEBAR_INNER_STYLE,
  SIDEBAR_MENU_STYLE,
  sidebarBrandStyle,
} from "./workspaceShellStyles";

interface AppSidebarProps {
  page: Page;
  currentUser: AuthUser;
  collapsed: boolean;
  onNavigate: (page: Page) => void;
  onToggleCollapse?: () => void;
  onItemClick?: () => void;
}

export function AppSidebar({
  page,
  currentUser,
  collapsed,
  onNavigate,
  onToggleCollapse,
  onItemClick,
}: AppSidebarProps) {
  const paperDisabled = !currentUser.can_paper_trade;
  const items = [...visiblePrimaryNav(currentUser), SETTINGS_NAV].map((item) => ({
    key: item.key,
    icon: item.icon,
    label: item.label,
    disabled: item.key === "paper" && paperDisabled,
    title: item.key === "paper" && paperDisabled ? "模拟盘需申请白名单权限" : undefined,
  }));

  return (
    <div style={SIDEBAR_INNER_STYLE}>
      <div style={sidebarBrandStyle(collapsed)}>{collapsed ? "维" : "维斯量化"}</div>
      <Menu
        theme="dark"
        mode="inline"
        inlineCollapsed={collapsed}
        selectedKeys={[page]}
        items={items}
        style={SIDEBAR_MENU_STYLE}
        onClick={({ key }) => {
          onNavigate(key as Page);
          onItemClick?.();
        }}
      />
      {onToggleCollapse ? (
        <div style={SIDEBAR_FOOTER_STYLE}>
          <Button
            type="text"
            size="small"
            style={SIDEBAR_COLLAPSE_BTN_STYLE}
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={onToggleCollapse}
            aria-label={collapsed ? "展开侧栏" : "收起侧栏"}
          />
        </div>
      ) : null}
    </div>
  );
}
