import React, { useState } from 'react';
import {
  Container,
  Header,
  Form,
  FormField,
  Input,
  Button,
  SpaceBetween,
  Alert,
  Box,
} from '@cloudscape-design/components';

export default function LoginPage({ onLogin }) {
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
    <Box padding={{ top: 'xxxl' }}>
      <div style={{ maxWidth: 420, margin: '0 auto' }}>
        <Container header={<Header variant="h2">Welcome Back</Header>}>
          <form onSubmit={handleSubmit}>
            <Form
              actions={
                <Button variant="primary" loading={loading} formAction="submit">
                  Sign In
                </Button>
              }
            >
              <SpaceBetween size="l">
                <FormField label="Email">
                  <Input
                    type="email"
                    value={email}
                    onChange={({ detail }) => setEmail(detail.value)}
                    placeholder="Email Address"
                  />
                </FormField>
                <FormField label="Password">
                  <Input
                    type="password"
                    value={password}
                    onChange={({ detail }) => setPassword(detail.value)}
                    placeholder="Password"
                  />
                </FormField>
                {error && <Alert type="error">{error}</Alert>}
                <Alert type="info">
                  <strong>Demo Credentials:</strong> testuser@example.com / TestPass123!
                </Alert>
              </SpaceBetween>
            </Form>
          </form>
        </Container>
      </div>
    </Box>
  );
}
