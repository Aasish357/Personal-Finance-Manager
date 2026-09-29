export function formatCurrency(amount: number): string {
  return amount.toLocaleString(undefined, { style: 'currency', currency: 'USD' });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function formatMonth(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long' });
}

/** YYYY-MM-01T00:00:00 for the given "YYYY-MM" input value, used when posting a budget. */
export function monthInputToIso(monthValue: string): string {
  return `${monthValue}-01T00:00:00`;
}

export function todayInputValue(): string {
  return new Date().toISOString().slice(0, 10);
}

export function currentMonthInputValue(): string {
  return new Date().toISOString().slice(0, 7);
}
