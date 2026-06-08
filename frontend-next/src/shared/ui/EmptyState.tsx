export function EmptyState(props: { text?: string }) {
  return <div class="tq-empty tq-empty-state">{props.text ?? "暂无数据"}</div>;
}
