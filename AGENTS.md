# AGENTS.md – AI Usage Documentation

## Overview

This project was developed with assistance from Claude (Anthropic), an AI
language model.

## How AI Was Used

| Area                | AI Contribution                                           |
| ------------------- | --------------------------------------------------------- |
| Architecture        | Recommended project structure and separation of concerns  |
| Code generation     | Produced initial source code for `main.py` and `utils.py` |
| Testing             | Generated pytest unit and integration tests               |
| CI/CD               | Created GitHub Actions workflow                           |
| Documentation       | Drafted README, docstrings, and this file                 |
| Config design       | Suggested YAML-based config to avoid hard-coded values    |

## Prompting Strategy

- Provided a clear specification with numbered requirements (data pull,
  processing, export, best practices).
- Asked for rationale on library choices (yfinance vs. alternatives).
- Requested step-by-step implementation with explanations.

## Human Review & Modifications

All AI-generated code was reviewed, tested, and modified as needed by the
project author before submission.
