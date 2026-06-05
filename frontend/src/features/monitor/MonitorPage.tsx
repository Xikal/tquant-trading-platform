import { memo } from "react";
import { MonitorActionPage, type MonitorActionPageProps } from "./MonitorActionPage";

export type MonitorPageProps = MonitorActionPageProps;

export const MonitorPage = memo(function MonitorPage(props: MonitorPageProps) {
  return <MonitorActionPage {...props} />;
});
