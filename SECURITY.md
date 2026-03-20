# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly using [GitHub's private vulnerability reporting](https://github.com/richtan/richtan/security/advisories/new).

Please do not open a public issue for security vulnerabilities.

## Scope

This project renders a GitHub profile README from API data. Security-relevant areas include:

- **HTML injection/XSS** in rendered output (repo names, descriptions, URLs)
- **GraphQL injection** via user-controlled input
- **Webhook signature bypass** in the Cloudflare Worker
- **Secret exposure** in logs, error messages, or committed files

