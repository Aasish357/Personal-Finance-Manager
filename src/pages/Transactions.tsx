import React, { useEffect, useMemo, useState } from 'react';
import * as categoryService from '../services/categoryService';
import * as transactionService from '../services/transactionService';
import { Category, Transaction, TransactionType } from '../types';
import { extractErrorMessage } from '../utils/errors';
import { formatCurrency, formatDate, todayInputValue } from '../utils/format';

const emptyForm = {
  amount: '',
  transaction_type: 'expense' as TransactionType,
  description: '',
  merchant: '',
  category_id: '',
  transaction_date: todayInputValue(),
};

const Transactions: React.FC = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [form, setForm] = useState(emptyForm);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // Non-null when the form is editing an existing row rather than creating one.
  const [editingId, setEditingId] = useState<string | null>(null);

  const categoryNameById = useMemo(() => {
    const map: Record<string, string> = {};
    categories.forEach((c) => (map[c.id] = c.name));
    return map;
  }, [categories]);

  const loadData = () => {
    setIsLoading(true);
    return Promise.all([transactionService.listTransactions(), categoryService.listCategories()])
      .then(([tx, cat]) => {
        setTransactions(tx);
        setCategories(cat);
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAddCategory = async () => {
    if (!newCategoryName.trim()) return;
    const category = await categoryService.createCategory(newCategoryName.trim());
    setCategories((prev) => [...prev, category].sort((a, b) => a.name.localeCompare(b.name)));
    setForm((f) => ({ ...f, category_id: category.id }));
    setNewCategoryName('');
  };

  const handleDelete = async (id: string) => {
    await transactionService.deleteTransaction(id);
    setTransactions((prev) => prev.filter((t) => t.id !== id));
  };

  /** Clicking Edit on a row loads it into the form above in "editing" mode. */
  const handleEdit = (t: Transaction) => {
    setEditingId(t.id);
    setForm({
      amount: String(t.amount),
      transaction_type: t.transaction_type,
      description: t.description || '',
      merchant: t.merchant || '',
      category_id: t.category_id || '',
      transaction_date: t.transaction_date.slice(0, 10),
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(emptyForm);
  };

  // In edit mode the form updates the existing row; otherwise it creates one.
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const payload = {
        amount: parseFloat(form.amount),
        transaction_type: form.transaction_type,
        description: form.description || undefined,
        merchant: form.merchant || undefined,
        category_id: form.category_id || undefined,
        transaction_date: `${form.transaction_date}T00:00:00`,
      };
      if (editingId) {
        await transactionService.updateTransaction(editingId, payload);
        setEditingId(null);
        setForm(emptyForm);
      } else {
        await transactionService.createTransaction(payload);
        setForm(emptyForm);
      }
      await loadData();
    } catch (err) {
      setError(extractErrorMessage(err, editingId ? 'Could not save those changes.' : 'Could not save that transaction.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isEditing = editingId !== null;

  return (
    <div>
      <div className="page-header">
        <h1>Transactions</h1>
        <p>Every dollar in and out, in one place.</p>
      </div>

      <div className="panel">
        <h2>{isEditing ? 'Edit transaction' : 'Add a transaction'}</h2>
        {error && <div className="form-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field-row">
            <div className="field">
              <label htmlFor="amount">Amount</label>
              <input
                id="amount"
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
                required
              />
            </div>
            <div className="field">
              <label htmlFor="type">Type</label>
              <select
                id="type"
                value={form.transaction_type}
                onChange={(e) => setForm({ ...form, transaction_type: e.target.value as TransactionType })}
              >
                <option value="expense">Expense</option>
                <option value="income">Income</option>
              </select>
            </div>
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="merchant">Merchant</label>
              <input
                id="merchant"
                type="text"
                value={form.merchant}
                onChange={(e) => setForm({ ...form, merchant: e.target.value })}
                placeholder="Optional"
              />
            </div>
            <div className="field">
              <label htmlFor="date">Date</label>
              <input
                id="date"
                type="date"
                value={form.transaction_date}
                onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="description">Description</label>
            <input
              id="description"
              type="text"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Optional"
            />
          </div>

          <div className="field">
            <label htmlFor="category">Category</label>
            <select
              id="category"
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
            >
              <option value="">Uncategorized</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field" style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
            <div style={{ flex: 1 }}>
              <label htmlFor="new-category">New category</label>
              <input
                id="new-category"
                type="text"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="e.g. Groceries"
              />
            </div>
            <button type="button" className="btn btn-secondary" onClick={handleAddCategory}>
              Add category
            </button>
          </div>

          {isEditing && (
            <button type="button" className="btn btn-secondary" onClick={cancelEdit} style={{ marginLeft: '0.6rem' }}>
              Cancel
            </button>
          )}
          <button className="btn" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Save transaction'}
          </button>
        </form>
      </div>

      <div className="panel">
        <h2>History</h2>
        {isLoading ? (
          <p>Loading…</p>
        ) : transactions.length === 0 ? (
          <div className="empty-state">
            <p>No transactions yet. Add your first one above.</p>
          </div>
        ) : (
          <table className="ledger">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Category</th>
                <th>Amount</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((t) => (
                <tr key={t.id}>
                  <td>{formatDate(t.transaction_date)}</td>
                  <td>
                    {t.description || t.merchant || '—'}
                    {t.merchant && t.description ? <div className="alert-meta">{t.merchant}</div> : null}
                  </td>
                  <td>{t.category_id ? categoryNameById[t.category_id] || '—' : '—'}</td>
                  <td className={t.transaction_type === 'income' ? 'amount-income' : 'amount-expense'}>
                    {t.transaction_type === 'income' ? '+' : '-'}
                    {formatCurrency(t.amount)}
                  </td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => handleEdit(t)}>
                      Edit
                    </button>{' '}
                    <button className="btn-danger btn" onClick={() => handleDelete(t.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default Transactions;
