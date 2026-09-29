import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { formatDate } from '../utils/format';

const Settings: React.FC = () => {
  const { user, logout } = useAuth();
  const [confirmingLogout, setConfirmingLogout] = useState(false);

  if (!user) return null;

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
        <p>Your account details.</p>
      </div>

      <div className="panel" style={{ maxWidth: 480 }}>
        <h2>Profile</h2>
        <table className="ledger">
          <tbody>
            <tr>
              <td style={{ color: 'var(--ink-soft)' }}>Name</td>
              <td>{user.name}</td>
            </tr>
            <tr>
              <td style={{ color: 'var(--ink-soft)' }}>Email</td>
              <td>{user.email}</td>
            </tr>
            <tr>
              <td style={{ color: 'var(--ink-soft)' }}>Member since</td>
              <td>{formatDate(user.created_at)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="panel" style={{ maxWidth: 480 }}>
        <h2>Session</h2>
        <p>Signing out clears your session on this device.</p>
        {confirmingLogout ? (
          <div style={{ display: 'flex', gap: '0.6rem' }}>
            <button className="btn btn-danger" onClick={logout}>
              Confirm sign out
            </button>
            <button className="btn btn-secondary" onClick={() => setConfirmingLogout(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <button className="btn btn-secondary" onClick={() => setConfirmingLogout(true)}>
            Sign out
          </button>
        )}
      </div>
    </div>
  );
};

export default Settings;
