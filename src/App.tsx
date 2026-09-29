import React from 'react';
import { BrowserRouter as Router, Redirect, Route, Switch } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Budgets from './pages/Budgets';
import Alerts from './pages/Alerts';
import FinanceAssistant from './pages/FinanceAssistant';
import Login from './pages/Login';
import Register from './pages/Register';
import Settings from './pages/Settings';

/** Keeps a signed-in user off the auth pages instead of showing them a login form. */
const GuestOnlyRoute: React.FC<{ path: string; children: React.ReactNode }> = ({ path, children }) => {
  const { user, isLoading } = useAuth();
  return (
    <Route
      path={path}
      render={() => {
        if (isLoading) return null;
        return user ? <Redirect to="/" /> : children;
      }}
    />
  );
};

const AppRoutes: React.FC = () => (
  <Switch>
    <GuestOnlyRoute path="/login">
      <Login />
    </GuestOnlyRoute>
    <GuestOnlyRoute path="/register">
      <Register />
    </GuestOnlyRoute>

    <ProtectedRoute path="/" exact>
      <Dashboard />
    </ProtectedRoute>
    <ProtectedRoute path="/transactions">
      <Transactions />
    </ProtectedRoute>
    <ProtectedRoute path="/budgets">
      <Budgets />
    </ProtectedRoute>
    <ProtectedRoute path="/alerts">
      <Alerts />
    </ProtectedRoute>
    <ProtectedRoute path="/assistant">
      <FinanceAssistant />
    </ProtectedRoute>
    <ProtectedRoute path="/settings">
      <Settings />
    </ProtectedRoute>
  </Switch>
);

const App: React.FC = () => {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  );
};

export default App;
