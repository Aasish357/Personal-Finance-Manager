export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Category {
  id: string;
  name: string;
  created_at: string;
}

export type TransactionType = 'income' | 'expense';

export interface Transaction {
  id: string;
  user_id: string;
  amount: number;
  transaction_type: TransactionType;
  description?: string;
  merchant?: string;
  category_id?: string;
  transaction_date: string;
  created_at: string;
  updated_at: string;
}

export interface Budget {
  id: string;
  user_id: string;
  category_id: string;
  month: string;
  amount: number;
  created_at: string;
  updated_at: string;
}

export interface Alert {
  id: string;
  user_id: string;
  budget_id: string;
  category_id: string;
  threshold: string;
  utilization: number;
  status: string;
  triggered_at: string;
  created_at: string;
}

export interface Overview {
  balance: number;
  total_income: number;
  total_expense: number;
  current_month_income: number;
  current_month_expense: number;
  active_alerts: number;
  transaction_count: number;
}

export interface MonthlyAnalytics {
  month: string;
  income: number;
  expense: number;
  net: number;
}

export interface CategoryAnalytics {
  category_id: string;
  category_name: string;
  amount: number;
  percentage: number;
}

export interface BudgetVsActual {
  budget_id: string;
  category_id: string;
  category_name: string;
  month: string;
  budgeted: number;
  spent: number;
  utilization_pct: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AssistantStatus {
  provider: string;
  base_url: string;
  model: string;
  available: boolean;
  model_installed: boolean;
  available_models: string[];
}
