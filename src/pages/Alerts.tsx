import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import * as alertService from '../services/alertService';
import { Alert } from '../types';
import { formatDate } from '../utils/format';

const Alerts: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = () => {
    setIsLoading(true);
    return alertService.listAlerts().then(setAlerts).finally(() => setIsLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleDismiss = async (id: string) => {
    const updated = await alertService.dismissAlert(id);
    setAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
  };

  const active = alerts.filter((a) => a.status === 'active');
  const closed = alerts.filter((a) => a.status !== 'active');
  // "resolved" is set by the system when the spending that triggered an alert
  // is deleted, so it needs its own label rather than being called dismissed.
  const closedTitle = closed.some((a) => a.status === 'resolved')
    ? 'Dismissed / resolved'
    : 'Dismissed';

  return (
    <div>
      <div className="page-header">
        <h1>Alerts</h1>
        <p>Raised automatically when a category crosses 75%, 90%, or 100% of its budget.</p>
      </div>

      <div className="panel">
        <h2>Active</h2>
        {isLoading ? (
          <p>Loading…</p>
        ) : active.length === 0 ? (
          <div className="empty-state">
            <p>Nothing active. Set budgets on the Budgets page to start tracking this.</p>
            <Link to="/budgets" className="btn">
              Go to budgets
            </Link>
          </div>
        ) : (
          active.map((a) => (
            <div className="alert-row" key={a.id}>
              <div>
                <strong>{a.threshold} of budget used</strong>
                <div className="alert-meta">
                  Utilization {a.utilization}% · triggered {formatDate(a.triggered_at)}
                </div>
              </div>
              <button className="btn btn-secondary" onClick={() => handleDismiss(a.id)}>
                Dismiss
              </button>
            </div>
          ))
        )}
      </div>

      {closed.length > 0 && (
        <div className="panel">
          <h2>{closedTitle}</h2>
          {closed.map((a) => (
            <div className="alert-row" key={a.id}>
              <div>
                <strong>{a.threshold} of budget used</strong>
                <div className="alert-meta">
                  Utilization {a.utilization}% · triggered {formatDate(a.triggered_at)}
                  {a.status === 'resolved' ? ' · spend was removed' : ''}
                </div>
              </div>
              <span className="tag">{a.status}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Alerts;
