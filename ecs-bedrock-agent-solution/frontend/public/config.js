// Local dev config — copy to public/config.js and fill in real values
window.APP_CONFIG = {
    cognito: {
        userPoolId: 'USER_POOL_ID',
        clientId: 'CLIENT_ID',
        region: 'REGION'
    },
    api: {
        endpoints: {
            chat: 'https://CLOUDFRONT_DISTRIBUTION_URL/api/chat'
        }
    }
};
