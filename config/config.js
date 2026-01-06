import allConfig from './env/all.js';
import developmentConfig from './env/development.js';
import productionConfig from './env/production.js';
import testConfig from './env/test.js';

// Determine environment (default to development if not set)
const env = process.env.NODE_ENV || 'development';

// Select environment-specific config
const envConfig = 
    env === 'development' ? developmentConfig :
    env === 'production' ? productionConfig :
    env === 'test' ? testConfig :
    {};

// Merge base config with environment-specific config (spread replaces _.extend)
export default {
    ...allConfig,
    ...envConfig
};