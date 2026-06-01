export function StockIdentity({ name, symbol }: { name?: string | null; symbol: string }) {
  return (
    <span className="tq-stock-identity">
      <strong>{name || symbol}</strong>
      <small>{symbol}</small>
    </span>
  );
}
