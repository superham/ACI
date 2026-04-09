# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in ACI, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please use [GitHub's private vulnerability reporting](https://github.com/superham/ACI/security/advisories/new) to submit your report. You should receive a response within 72 hours. If accepted, a fix will be developed privately and released as a patch version.

## Scope

ACI is a data analysis CLI tool that:
- Makes outbound API calls to ransomware.live and ransomwhere.re
- Processes and stores data locally
- Does not run a web server or accept inbound network connections

Security concerns most relevant to this project include:
- Dependency vulnerabilities (especially in torch, requests, pandas)
- API key exposure in logs or outputs
- Injection via malformed API response data
