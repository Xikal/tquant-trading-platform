export function plainMarketText(marketState?: string | null) {
  switch (marketState) {
    case "broad_rally":
      return "强势主升，可提高关注";
    case "repair":
      return "弱势修复，只适合小仓试错";
    case "fast_rotation":
      return "轮动太快，只做最强主线";
    case "weight_support":
      return "指数被权重托住，题材股别追高";
    case "high_flyer_retreat":
      return "高位退潮，先别买";
    case "risk_release":
      return "风险释放中，空仓等待";
    case "low_volume_wait":
      return "缩量无主线，等放量确认";
    default:
      return "环境一般，小仓观察";
  }
}

export function plainHoldingAction(action?: string | null, riskLevel?: string | null) {
  if (riskLevel === "high") {
    return "风险偏高，先别加仓";
  }
  switch (action) {
    case "positive_t":
      return "现在能买回";
    case "negative_t":
      return "现在能卖一部分";
    default:
      return "今天别动";
  }
}

export function plainRiskText(riskLevel?: string | null) {
  switch (riskLevel) {
    case "low":
      return "风险低";
    case "high":
      return "风险高";
    default:
      return "风险中等";
  }
}
