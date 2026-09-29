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

export async function listTransactions(): Promise<Transaction[]> {
  const { data } = await apiClient.get<Transaction[]>('/transactions');
  return data;
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
