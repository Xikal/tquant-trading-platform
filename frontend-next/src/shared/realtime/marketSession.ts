export function isLikelyTradingTime(now = new Date()): boolean {
  const day = now.getDay();
  if (day === 0 || day === 6) return false;
  const minutes = now.getHours() * 60 + now.getMinutes();
  return (minutes >= 9 * 60 + 25 && minutes <= 11 * 60 + 35) || (minutes >= 13 * 60 && minutes <= 15 * 60 + 5);
}

export function formatMarketClock(now = new Date()): string {
  return now.toLocaleTimeString("zh-CN", { hour12: false });
}
