/** Small shared UI/formatting helpers. */

/** Format an atomic USDX amount (6 decimals) as a human dollar string. */
export function formatUsdx(amountAtomic: number, decimals = 6): string {
  const value = amountAtomic / 10 ** decimals;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(value);
}

/** Join class names, dropping falsy values. */
export function cn(
  ...classes: Array<string | false | null | undefined>
): string {
  return classes.filter(Boolean).join(" ");
}

/** Truncate a hex address/hash to `0x1234…abcd`. */
export function shortHash(value: string, lead = 6, tail = 4): string {
  if (value.length <= lead + tail) return value;
  return `${value.slice(0, lead)}…${value.slice(-tail)}`;
}
