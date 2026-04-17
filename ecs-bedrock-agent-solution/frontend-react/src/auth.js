import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
} from 'amazon-cognito-identity-js';

let userPool = null;
let cognitoUser = null;
let currentSession = null;

function getPool() {
  if (!userPool) {
    const cfg = window.APP_CONFIG?.cognito;
    if (!cfg) throw new Error('APP_CONFIG not loaded');
    userPool = new CognitoUserPool({
      UserPoolId: cfg.userPoolId,
      ClientId: cfg.clientId,
    });
  }
  return userPool;
}

export function restoreSession() {
  return new Promise((resolve) => {
    try {
      const user = getPool().getCurrentUser();
      if (!user) return resolve(null);
      user.getSession((err, session) => {
        if (err || !session?.isValid()) return resolve(null);
        cognitoUser = user;
        currentSession = session;
        resolve({
          email: user.getUsername(),
          token: session.getIdToken().getJwtToken(),
        });
      });
    } catch {
      resolve(null);
    }
  });
}

export function login(email, password) {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: getPool() });
    user.authenticateUser(
      new AuthenticationDetails({ Username: email, Password: password }),
      {
        onSuccess: (result) => {
          cognitoUser = user;
          currentSession = result;
          resolve({
            email,
            token: result.getIdToken().getJwtToken(),
          });
        },
        onFailure: reject,
      }
    );
  });
}

export function logout() {
  cognitoUser?.signOut();
  cognitoUser = null;
  currentSession = null;
}

export function getToken() {
  return currentSession?.getIdToken()?.getJwtToken();
}
