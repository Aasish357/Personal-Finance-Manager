import apiClient from './apiClient';
import { Budget } from '../types';

export interface NewBudget {
  category_id: string;
  month: string;
  amount: number;
}

export async function listBudgets(): Promise<Budget[]> {
  const { data } = await apiClient.get<Budget[]>('/budgets');
  return data;
}

export async function createBudget(payload: NewBudget): Promise<Budget> {
  const { data } = await apiClient.post<Budget>('/budgets', payload);
  return data;
}

export async function deleteBudget(id: string): Promise<void> {
  await apiClient.delete(`/budgets/${id}`);
}
