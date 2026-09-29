import apiClient from './apiClient';
import { AuthResponse, User } from '../types';

export async function register(name: string, email: string, password: string): Promise<User> {
  const { data } = await apiClient.post<User>('/auth/register', { name, email, password });
  return data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>('/auth/login', { email, password });
  return data;
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me');
  return data;
}
