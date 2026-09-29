import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import * as analyticsService from '../services/analyticsService';
import * as alertService from '../services/alertService';
import { Alert, CategoryAnalytics, MonthlyAnalytics, Overview } from '../types';
import { formatCurrency, formatMonth } from '../utils/format';

const Dashboard: React.FC = () => {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [monthly, setMonthly] = useState<MonthlyAnalytics[]>([]);
  const [categories, setCategories] = useState<CategoryAnalytics[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      analyticsService.getOverview(),
      analyticsService.getMonthly(),
      analyticsService.getCategoryBreakdown(),
      alertService.listAlerts(),
    ])
      .then(([ov, mo, cat, al]) => {
        setOverview(ov);
        setMonthly(mo.slice(-6));
        setCategories(cat.slice(0, 6));
        setAlerts(al.filter((a) => a.status === 'active').slice(0, 3));
      })
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return <p>Loading your overview…</p>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Where things stand right now.</p>
      </div>

      {overview && (
        <div className="stat-row">
          <div className="stat">
            <div className="stat-label">Balance</div>
            <div className={`stat-value ${overview.balance >= 0 ? 'positive' : 'negative'}`}>
              {formatCurrency(overview.balance)}
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">This month, in</div>
            <div className="stat-value positive">{formatCurrency(overview.current_month_income)}</div>
          </div>
          <div className="stat">
            <div className="stat-label">This month, out</div>
            <div className="stat-value negative">{formatCurrency(overview.current_month_expense)}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Active alerts</div>
            <div className="stat-value">{overview.active_alerts}</div>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-title-row">
          <h2>Recent months</h2>
          <Link to="/transactions">View transactions</Link>
        </div>
        {monthly.length === 0 ? (
          <div className="empty-state">
            <p>No transactions yet — once you log a few, monthly trends show up here.</p>
            <Link to="/transactions" className="btn">
              Add a transaction
            </Link>
          </div>
        ) : (
          <table className="ledger">
            <thead>
              <tr>
                <th>Month</th>
                <th>Income</th>
                <th>Expense</th>
                <th>Net</th>
              </tr>
            </thead>
            <tbody>
              {monthly.map((m) => (
                <tr key={m.month}>
                  <td>{formatMonth(`${m.month}-01`)}</td>
                  <td className="amount-income">{formatCurrency(m.income)}</td>
                  <td className="amount-expense">{formatCurrency(m.expense)}</td>
                  <td className={m.net >= 0 ? 'amount-income' : 'amount-expense'}>{formatCurrency(m.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <div className="panel-title-row">
          <h2>Spending by category</h2>
        </div>
        {categories.length === 0 ? (
          <div className="empty-state">
            <p>Nothing to break down yet.</p>
          </div>
        ) : (
          <div>
            {categories.map((c) => (
              <div key={c.category_id} style={{ marginBottom: '0.9rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                  <span>{c.category_name}</span>
                  <span>
                    {formatCurrency(c.amount)} · {c.percentage}%
                  </span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${Math.min(c.percentage, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-title-row">
          <h2>Active alerts</h2>
          <Link to="/alerts">View all</Link>
        </div>
        {alerts.length === 0 ? (
          <div className="empty-state">
            <p>No active alerts. Everything's under budget.</p>
          </div>
        ) : (
          alerts.map((a) => (
            <div className="alert-row" key={a.id}>
              <div>
                <strong>{a.threshold} of budget used</strong>
                <div className="alert-meta">Utilization {a.utilization}%</div>
              </div>
              <span className="tag">{a.status}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Dashboard;
