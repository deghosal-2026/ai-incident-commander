# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in ai-incident-commander, please report it privately. **Do not open a public GitHub issue.**

Send details to the project maintainers via GitHub's security advisory feature:

1. Go to https://github.com/deghosal-2026/ai-incident-commander/security/advisories
2. Click "New advisory"
3. Fill in the details

Alternatively, email the maintainers directly (see GitHub profile for contact info).

## Response Timeline

- **Acknowledgement:** Within 48 hours of report
- **Triaged:** Within 5 business days
- **Fix released:** Within 30 days (depending on severity)

## What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Any proposed fix (optional)

## Scope

This project is a CLI tool that processes incident data locally. It does not:

- Expose a network service
- Store credentials in source code
- Send data to third parties (LLM calls go to user-configured endpoints)
- Execute production changes

## Responsible Disclosure

Please allow time for a fix before disclosing the vulnerability publicly. We will coordinate disclosure with you once a fix is available.
