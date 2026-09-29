import React from 'react';
import { Redirect, Route, RouteProps } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import AppLayout from './AppLayout';

interface ProtectedRouteProps extends Omit<RouteProps, 'children' | 'component' | 'render'> {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, ...rest }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="auth-page">
        <p>Loading…</p>
      </div>
    );
  }

  return (
    <Route
      {...rest}
      render={() =>
        user ? <AppLayout>{children}</AppLayout> : <Redirect to="/login" />
      }
    />
  );
};

export default ProtectedRoute;
