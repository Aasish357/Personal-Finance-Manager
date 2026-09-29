import { AxiosError } from 'axios';

export function extractErrorMessage(err: unknown, fallback = 'Something went wrong. Please try again.'): string {
  const axiosErr = err as AxiosError<{ detail?: string | { msg: string }[] }>;
  const detail = axiosErr?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return fallback;
}
