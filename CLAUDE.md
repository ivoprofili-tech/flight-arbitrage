# CLAUDE.md

## Project Overview

**flight-arbitrage** is a project for flight price arbitrage. The repository is in its initial stage of development.

- **Repository**: ivoprofili-tech/flight-arbitrage
- **Created**: January 2026
- **Status**: Early development (scaffold only)

## Repository Structure

```
flight-arbitrage/
├── CLAUDE.md          # This file - AI assistant guide
└── README.md          # Project readme
```

No application code, configuration files, or dependencies have been added yet.

## Development Setup

### Prerequisites

Not yet defined. Update this section when the tech stack is chosen.

### Getting Started

```bash
git clone <repository-url>
cd flight-arbitrage
# Additional setup steps TBD
```

## Build & Test Commands

No build system or test framework has been configured yet. Update this section as tooling is added.

<!-- Example placeholders for future use:
- `npm install` - Install dependencies
- `npm run build` - Build the project
- `npm test` - Run all tests
- `npm run test:single -- path/to/test` - Run a single test
- `npm run lint` - Run linter
- `npm run lint:fix` - Auto-fix lint issues
-->

## Code Conventions

### General Guidelines

- Keep code simple and focused; avoid over-engineering
- Write clear commit messages that explain the "why"
- Add tests for new functionality
- Validate inputs at system boundaries (user input, external APIs)
- Do not commit secrets, API keys, or credentials

### Git Workflow

- Use feature branches for development
- Branch naming: `feature/<description>`, `fix/<description>`, `chore/<description>`
- Keep commits atomic and focused on a single change

## Architecture

Architecture has not yet been defined. Update this section when the application structure is established.

## Key Files Reference

| File | Purpose |
|------|---------|
| `README.md` | Project overview and user-facing documentation |
| `CLAUDE.md` | AI assistant guide and developer reference |

## Environment Variables

No environment variables are configured yet. Document them here as they are added:

<!-- Example:
| Variable | Description | Required |
|----------|-------------|----------|
| `API_KEY` | Flight data API key | Yes |
-->

## Common Tasks for AI Assistants

When working on this repository:

1. **Before making changes**: Read relevant files first; never modify code you haven't read
2. **Keep it minimal**: Only add what is explicitly requested
3. **Update this file**: When adding new tooling, commands, or architectural decisions, update CLAUDE.md to reflect them
4. **No unnecessary files**: Don't create documentation or config files unless specifically asked
5. **Security**: Never commit `.env` files or secrets; use `.gitignore` appropriately
