import type { AiInsight } from "./analysis";

export type AiDecisionTask =
  | "stock_explain"
  | "daily_review"
  | "strategy_attribution"
  | "priority_board_summary"
  | "event_risk_summary";

export interface AiDecisionSupportRequest {
  task: AiDecisionTask;
  title?: string;
  payload: Record<string, unknown>;
  include_ai?: boolean;
}

export interface AiDecisionSupportResponse {
  task: AiDecisionTask;
  title: string;
  insight: AiInsight;
  model: string;
  provider: string;
  fixed_sections?: {
    can_buy: string;
    why: string;
    main_risk: string;
    tomorrow_plan: string;
  };
}
