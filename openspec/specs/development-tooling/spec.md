# development-tooling

## Purpose

TBD

## Requirements

### Requirement: Frontend linting and formatting
The frontend system SHALL support code linting via ESLint and automatic formatting via Prettier.

#### Scenario: Running frontend quality checks
- **WHEN** the developer executes `npm run lint` in the `ui` directory
- **THEN** ESLint analyzes the TypeScript and React files and reports any style or syntax errors

### Requirement: Backend linting and formatting
The Python backend system SHALL support linting and formatting via Ruff.

#### Scenario: Running backend formatting and linting checks
- **WHEN** the developer executes `ruff check` and `ruff format` at the project root
- **THEN** Ruff analyzes and formats the Python files according to the defined style rules

### Requirement: Frontend unit testing
The frontend system SHALL support unit testing via Vitest.

#### Scenario: Executing frontend tests
- **WHEN** the developer runs `npm run test` or `npm run test:run` in the `ui` directory
- **THEN** Vitest executes the suite of React unit tests and outputs the pass/fail results

### Requirement: Backend unit testing
The Python backend system SHALL support unit testing via pytest.

#### Scenario: Executing backend tests
- **WHEN** the developer runs `pytest` at the project root
- **THEN** pytest runs all test cases and reports the coverage and execution details
