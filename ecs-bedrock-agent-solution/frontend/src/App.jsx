import React, { useState, useEffect } from 'react';
import TopNavigation from '@cloudscape-design/components/top-navigation';
import AppLayout from '@cloudscape-design/components/app-layout';
import Flashbar from '@cloudscape-design/components/flashbar';
import LoginForm from './components/LoginForm';
import ChatView from './components/ChatView';
import { initCognito, getCurrentSession, login as cognitoLogin, logout as cognitoLogout } from './services/auth';

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [flashItems, setFlashItems] = useState([]);

  useEffect(() => {
    initCognito();
    getCurrentSession()
      .then((u) => setUser(u))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleLogin = async (email, password) => {
    try {
      const u = await cognitoLogin(email, password);
      setUser(u);
      setFlashItems([]);
    } catch (err) {
      setFlashItems([
        {
          type: 'error',
          dismissible: true,
          content: err.message || 'Login failed',
          id: 'login-error',
          onDismiss: () => setFlashItems([]),
        },
      ]);
      throw err;
    }
  };

  const handleLogout = () => {
    cognitoLogout();
    setUser(null);
    setFlashItems([]);
  };

  const addFlash = (item) => {
    const id = `flash-${Date.now()}`;
    setFlashItems((prev) => [
      ...prev,
      { ...item, id, dismissible: true, onDismiss: () => setFlashItems((f) => f.filter((i) => i.id !== id)) },
    ]);
  };

  if (loading) return null;

  return (
    <>
      <TopNavigation
        identity={{
          href: '#',
          title: '🛡️ AWS Well-Architected Security Assistant',
        }}
        utilities={
          user
            ? [
                {
                  type: 'button',
                  text: user.email,
                  iconName: 'user-profile',
                },
                {
                  type: 'button',
                  text: 'Logout',
                  onClick: handleLogout,
                },
              ]
            : []
        }
      />
      <AppLayout
        navigationHide
        toolsHide
        notifications={<Flashbar items={flashItems} />}
        content={
          user ? (
            <ChatView user={user} onError={addFlash} />
          ) : (
            <LoginForm onLogin={handleLogin} flashItems={flashItems} />
          )
        }
      />
    </>
  );
}
