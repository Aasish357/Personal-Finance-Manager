import apiClient from './apiClient';
import { AssistantStatus, ChatMessage } from '../types';

export async function sendChatMessage(message: string, history: ChatMessage[]): Promise<string> {
  const { data } = await apiClient.post<{ reply: string; generated_at: string }>('/assistant/chat', {
    message,
    history,
  });
  return data.reply;
}

/** Which local model is configured, and whether Ollama is actually reachable. */
export async function getStatus(): Promise<AssistantStatus> {
  const { data } = await apiClient.get<AssistantStatus>('/assistant/status');
  return data;
}
