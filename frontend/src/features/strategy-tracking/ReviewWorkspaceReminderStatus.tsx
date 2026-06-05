import { Tag } from "antd";
import type { ReviewWorkspaceResponse } from "../../types";

export function ReviewWorkspaceReminderStatus({ reminder }: { reminder?: ReviewWorkspaceResponse["reminder"] }) {
  if (!reminder) return null;
  return (
    <section className={`strategy-review-reminder status-${reminder.status}`}>
      <strong>收盘后复盘：{reminder.message}</strong>
      <span>
        {reminder.refresh_queued ? <Tag>刷新已排队</Tag> : null}
        <Tag>{statusText(reminder.status)}</Tag>
        该状态只提醒复盘池是否可用，不发送买卖建议。
      </span>
    </section>
  );
}

function statusText(status: string) {
  if (status === "ready") return "已生成";
  if (status === "queued") return "已排队";
  if (status === "refreshing") return "刷新中";
  if (status === "insufficient") return "数据不足";
  if (status === "blocked") return "已关闭";
  return "未到收盘";
}
