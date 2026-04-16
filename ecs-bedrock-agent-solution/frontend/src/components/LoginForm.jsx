import React, { useState } from 'react';
import Container from '@cloudscape-design/components/container';
import Header from '@cloudscape-design/components/header';
import SpaceBetween from '@cloudscape-design/components/space-between';
import FormField from '@cloudscape-design/components/form-field';
import Input from '@cloudscape-design/components/input';
import Button from '@cloudscape-design/components/button';
import Box from '@cloudscape-design/components/box';
import Link from '@cloudscape-design/components/link';

export default function LoginForm({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onLogin(email, password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box margin={{ top: 'xxxl' }} padding={{ horizontal: 'xxxl' }}>
      <div style={{ maxWidth: 420, margin: '0 auto' }}>
        <Container header={<Header variant="h1">Welcome Back</Header>}>
          <form onSubmit={handleSubmit}>
            <SpaceBetween size="l">
              <FormField label="Email Address">
                <Input
                  type="email"
                  placeholder="Email Address"
                  value={email}
                  onChange={({ detail }) => setEmail(detail.value)}
                />
              </FormField>
              <FormField label="Password" errorText={error || undefined}>
                <Input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={({ detail }) => setPassword(detail.value)}
                />
              </FormField>
              <Button variant="primary" loading={loading} formAction="submit" onClick={handleSubmit} fullWidth>
                Sign In
              </Button>
              <Box
                variant="div"
                padding="s"
                color="text-body-secondary"
                fontSize="body-s"
                textAlign="center"
              >
                <Box fontWeight="bold" color="text-status-warning">
                  Demo Credentials
                </Box>
                Email: testuser@example.com
                <br />
                Password: TestPass123!
              </Box>
            </SpaceBetween>
          </form>
        </Container>
      </div>
    </Box>
  );
}
