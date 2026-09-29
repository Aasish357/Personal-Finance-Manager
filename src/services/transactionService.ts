import apiClient from './apiClient';
import { Transaction, TransactionType } from '../types';

export interface NewTransaction {
  amount: number;
  transaction_type: TransactionType;
  description?: string;
  merchant?: string;
  category_id?: string;
  transaction_date: string;
}

export interface TransactionPage {
  transactions: Transaction[];
  total: number;
}

/**
 * Newest first. `limit`/`offset` are optional -- omit them and you get
 * everything, which is what the callers that just want a list do. The total
 * arrives in the X-Total-Count header.
 */
export async function listTransactions(
  params: { limit?: number; offset?: number } = {}
): Promise<TransactionPage> {
  const { data, headers } = await apiClient.get<Transaction[]>('/transactions', { params });
  const total = Number(headers['x-total-count'] ?? data.length);
  return { transactions: data, total };
}

export async function createTransaction(payload: NewTransaction): Promise<Transaction> {
  const { data } = await apiClient.post<Transaction>('/transactions', payload);
  return data;
}

export async function deleteTransaction(id: string): Promise<void> {
  await apiClient.delete(`/transactions/${id}`);
}

/** Partial update -- only the fields you pass are changed. */
export async function updateTransaction(
  id: string,
  payload: Partial<NewTransaction>
): Promise<Transaction> {
  const { data } = await apiClient.patch<Transaction>(`/transactions/${id}`, payload);
  return data;
}
