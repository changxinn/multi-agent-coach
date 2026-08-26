# Environment Configuration Files

This folder contains environment-specific configuration files for different deployment stages.

## Files

- `.env.development` - Local development environment
- `.env.qa` - QA/Staging environment  
- `.env.production` - Production environment

## Usage

These files are automatically loaded by Vite based on the `--mode` flag:

```bash
# Development (default)
npm run dev              # Uses .env.development

# QA
npm run dev:qa           # Uses .env.qa
npm run build:qa         # Uses .env.qa

# Production
npm run dev:prod         # Uses .env.production
npm run build            # Uses .env.production
npm run build:prod       # Uses .env.production
```

## Security

⚠️ **Do not commit sensitive data** to these files if they contain real secrets. Use CI/CD secrets management for production credentials.
