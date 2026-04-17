// AWS Configuration for Cloud Optimization Web Interface
// This file is generated during deployment — do not edit manually.
window.APP_CONFIG = {
  cognito: {
    userPoolId: 'USER_POOL_ID',
    clientId: 'CLIENT_ID',
    region: 'REGION',
  },
  api: {
    endpoints: {
      chat: 'https://CLOUDFRONT_DISTRIBUTION_URL/api/chat',
    },
  },
};
