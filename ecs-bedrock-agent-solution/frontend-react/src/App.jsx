import React, { useState, useEffect } from 'react';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import AppLayout from '@cloudscape-design/components/app-layout';
import Spinner from '@cloudscape-design/components/spinner';
import Box from '@cloudscape-design/components/box';
import LoginPage from './LoginPage';
import ChatPage from './ChatPage';
import { login as authLogin, logout as authLogout, restoreSession } from './auth';

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    restoreSession().then((u) => {
      if (u) setUser(u);
      setLoading(false);
    });
  }, []);

  const handleLogin = async (email, password) => {
    const u = await authLogin(email, password);
    setUser(u);
  };

  const handleLogout = () => {
    authLogout();
    setUser(null);
  };

  if (loading) {
    return (
      <Box textAlign="center" padding={{ top: 'xxxl' }}>
        <Spinner size="large" />
      </Box>
    );
  }

  return (
    <>
      <TopNavigation
        identity={{
          href: '#',
          title: '🛡️ AWS Well-Architected Security Assistant',
        }}
        utilities={
          user
            ? [{ type: 'button', text: user.email }, { type: 'button', text: 'Sign out', onClick: handleLogout }]
            : []
        }
      />
      <AppLayout
        navigationHide
        toolsHide
        content={
          user ? (
            <ChatPage user={user} onLogout={handleLogout} />
          ) : (
            <LoginPage onLogin={handleLogin} />
          )
        }
      />
    </>
  );
}
