import apiClient from './apiClient';
import { BudgetVsActual, CategoryAnalytics, MonthlyAnalytics, Overview } from '../types';

export async function getOverview(): Promise<Overview> {
  const { data } = await apiClient.get<Overview>('/analytics/overview');
  return data;
}

export async function getMonthly(): Promise<MonthlyAnalytics[]> {
  const { data } = await apiClient.get<MonthlyAnalytics[]>('/analytics/monthly');
  return data;
}

export async function getCategoryBreakdown(): Promise<CategoryAnalytics[]> {
  const { data } = await apiClient.get<CategoryAnalytics[]>('/analytics/categories');
  return data;
}

export async function getBudgetVsActual(): Promise<BudgetVsActual[]> {
  const { data } = await apiClient.get<BudgetVsActual[]>('/analytics/budget-vs-actual');
  return data;
}
