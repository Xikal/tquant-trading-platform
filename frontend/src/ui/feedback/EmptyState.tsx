import type { ReactNode } from "react";
import { TqEmpty } from "./StateViews";

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <TqEmpty title={title} description={description} action={action} />;
}
