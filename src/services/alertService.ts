import apiClient from './apiClient';
import { Alert } from '../types';

export async function listAlerts(): Promise<Alert[]> {
  const { data } = await apiClient.get<Alert[]>('/alerts');
  return data;
}

export async function dismissAlert(id: string): Promise<Alert> {
  const { data } = await apiClient.post<Alert>(`/alerts/${id}/dismiss`);
  return data;
}
