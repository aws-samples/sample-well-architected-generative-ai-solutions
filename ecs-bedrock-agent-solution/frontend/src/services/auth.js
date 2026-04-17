import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js';

let userPool = null;

export function initCognito() {
  const cfg = window.APP_CONFIG?.cognito;
  if (!cfg) {
    console.error('APP_CONFIG.cognito not found — is config.js loaded?');
    return;
  }
  userPool = new CognitoUserPool({
    UserPoolId: cfg.userPoolId,
    ClientId: cfg.clientId,
  });
}

/** Resolve current session or reject */
export function getCurrentSession() {
  return new Promise((resolve, reject) => {
    if (!userPool) return reject(new Error('Pool not initialised'));
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) return reject(new Error('No current user'));
    cognitoUser.getSession((err, session) => {
      if (err || !session?.isValid()) return reject(err || new Error('Invalid session'));
      resolve({
        email: cognitoUser.getUsername(),
        token: session.getIdToken().getJwtToken(),
        cognitoUser,
      });
    });
  });
}

/** Authenticate with email + password */
export function login(email, password) {
  return new Promise((resolve, reject) => {
    if (!userPool) return reject(new Error('Pool not initialised'));
    const cognitoUser = new CognitoUser({ Username: email, Pool: userPool });
    const authDetails = new AuthenticationDetails({ Username: email, Password: password });
    cognitoUser.authenticateUser(authDetails, {
      onSuccess: (result) =>
        resolve({
          email,
          token: result.getIdToken().getJwtToken(),
          cognitoUser,
        }),
      onFailure: (err) => reject(err),
    });
  });
}

export function logout() {
  const cognitoUser = userPool?.getCurrentUser();
  if (cognitoUser) cognitoUser.signOut();
}
