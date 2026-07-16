# Issue tracker: GitHub

Issues and product requirements documents for this repository live as GitHub
issues. Use the `gh` CLI for all operations and infer the repository from the
current clone's `origin` remote.

## Conventions

- Create an issue with `gh issue create`.
- Read an issue and its discussion with `gh issue view <number> --comments`.
- Apply or remove labels with `gh issue edit`.
- Close resolved work with `gh issue close` and a concise outcome comment.

## Pull requests as a triage surface

PRs as a request surface: no. External pull requests are not included in the
issue triage queue unless this policy is changed here deliberately.

## Skill routing

When an engineering skill says to publish to the issue tracker, create a GitHub
issue. When it asks for the relevant ticket, read the corresponding GitHub issue
including its comments and labels.
