import React, { useEffect, useMemo, useState } from 'react';
import * as budgetService from '../services/budgetService';
import * as categoryService from '../services/categoryService';
import * as analyticsService from '../services/analyticsService';
import { Budget, BudgetVsActual, Category } from '../types';
import { extractErrorMessage } from '../utils/errors';
import { currentMonthInputValue, formatCurrency, formatMonth, monthInputToIso } from '../utils/format';

const emptyForm = {
  category_id: '',
  month: currentMonthInputValue(),
  amount: '',
};

const Budgets: React.FC = () => {
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [actuals, setActuals] = useState<BudgetVsActual[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const actualsByBudgetId = useMemo(() => {
    const map: Record<string, BudgetVsActual> = {};
    actuals.forEach((a) => (map[a.budget_id] = a));
    return map;
  }, [actuals]);

  const loadData = () => {
    setIsLoading(true);
    return Promise.all([
      budgetService.listBudgets(),
      categoryService.listCategories(),
      analyticsService.getBudgetVsActual(),
    ])
      .then(([b, c, a]) => {
        setBudgets(b);
        setCategories(c);
        setActuals(a);
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.category_id) {
      setError('Choose a category first — add one from the Transactions page if the list is empty.');
      return;
    }
    setIsSubmitting(true);
    try {
      await budgetService.createBudget({
        category_id: form.category_id,
        month: monthInputToIso(form.month),
        amount: parseFloat(form.amount),
      });
      setForm(emptyForm);
      await loadData();
    } catch (err) {
      setError(extractErrorMessage(err, 'Could not save that budget.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    await budgetService.deleteBudget(id);
    setBudgets((prev) => prev.filter((b) => b.id !== id));
  };

  return (
    <div>
      <div className="page-header">
        <h1>Budgets</h1>
        <p>Set a monthly ceiling per category — alerts fire automatically once you're close.</p>
      </div>

      <div className="panel">
        <h2>Set a budget</h2>
        {error && <div className="form-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="field-row">
            <div className="field">
              <label htmlFor="category">Category</label>
              <select
                id="category"
                value={form.category_id}
                onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              >
                <option value="">Select a category</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="month">Month</label>
              <input
                id="month"
                type="month"
                value={form.month}
                onChange={(e) => setForm({ ...form, month: e.target.value })}
                required
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="amount">Monthly limit</label>
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
          <button className="btn" type="submit" disabled={isSubmitting || categories.length === 0}>
            {isSubmitting ? 'Saving…' : 'Set budget'}
          </button>
          {categories.length === 0 && (
            <p className="alert-meta" style={{ marginTop: '0.6rem' }}>
              No categories yet — add one from the Transactions page first.
            </p>
          )}
        </form>
      </div>

      <div className="panel">
        <h2>Your budgets</h2>
        {isLoading ? (
          <p>Loading…</p>
        ) : budgets.length === 0 ? (
          <div className="empty-state">
            <p>No budgets set yet. Add one above to start tracking utilization.</p>
          </div>
        ) : (
          budgets.map((b) => {
            const actual = actualsByBudgetId[b.id];
            const pct = actual?.utilization_pct ?? 0;
            return (
              <div key={b.id} style={{ marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <div>
                    <strong>{actual?.category_name || '—'}</strong>
                    <div className="alert-meta">{formatMonth(b.month)}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div>
                      {formatCurrency(actual?.spent ?? 0)} of {formatCurrency(b.amount)}
                    </div>
                    <button className="btn-danger btn" onClick={() => handleDelete(b.id)} style={{ marginTop: '0.4rem' }}>
                      Remove
                    </button>
                  </div>
                </div>
                <div className="progress-track">
                  <div
                    className={`progress-fill ${pct >= 100 ? 'over' : ''}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default Budgets;
