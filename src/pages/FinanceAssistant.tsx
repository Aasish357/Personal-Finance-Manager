import React, { useEffect, useRef, useState } from 'react';
import * as assistantService from '../services/assistantService';
import { AssistantStatus, ChatMessage } from '../types';
import { extractErrorMessage } from '../utils/errors';

const SUGGESTIONS = ["What's my balance?", 'Am I over budget anywhere?', 'How much have I spent this month?'];

const FinanceAssistant: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: "Hi — ask me about your balance, this month's spending, or your budgets." },
  ]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages]);

  // Surface which local model is answering, so odd replies are easy to trace
  // back to the model rather than looking like a data problem.
  useEffect(() => {
    assistantService
      .getStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const send = async (text: string) => {
    if (!text.trim() || isSending) return;
    setError(null);
    const history = messages;
    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setInput('');
    setIsSending(true);
    try {
      const reply = await assistantService.sendChatMessage(text, history);
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }]);
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't reach the assistant."));
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    send(input);
  };

  return (
    <div>
      <div className="page-header">
        <h1>Assistant</h1>
        <p>Ask questions about your own spending — answers are grounded in your actual transactions.</p>
      </div>

      {status && !status.available && (
        <div className="form-error" style={{ marginBottom: '1rem' }}>
          Can't reach Ollama at {status.base_url}. Replies will come from the
          built-in fallback — still computed from your real data, but not
          conversational. On a cloud host there is no local Ollama, so point{' '}
          <code>OLLAMA_BASE_URL</code> at a machine that runs it, or accept the fallback.
        </div>
      )}
      {status && status.available && !status.model_installed && (
        <div className="form-error" style={{ marginBottom: '1rem' }}>
          Ollama is running but <code>{status.model}</code> isn't installed. Pull it with{' '}
          <code>ollama pull {status.model}</code>.
        </div>
      )}

      <div className="chat-window">
        <div className="chat-log" ref={logRef}>
          {messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              {m.content}
            </div>
          ))}
          {isSending && <div className="chat-bubble assistant">Thinking…</div>}
        </div>
        <form className="chat-input-row" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your finances…"
            disabled={isSending}
          />
          <button className="btn" type="submit" disabled={isSending}>
            Send
          </button>
        </form>
      </div>

      {error && (
        <div className="form-error" style={{ marginTop: '1rem' }}>
          {error}
        </div>
      )}

      <div className="chat-suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chat-suggestion" onClick={() => send(s)} disabled={isSending}>
            {s}
          </button>
        ))}
      </div>

      {status && (
        <p className="alert-meta" style={{ marginTop: '1rem' }}>
          Answering with <code>{status.model}</code> via {status.provider} on {status.base_url}
        </p>
      )}
    </div>
  );
};

export default FinanceAssistant;
