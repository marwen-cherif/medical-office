## ADDED Requirements

### Requirement: Centralized task execution
The system SHALL support unified task execution for both frontend and backend from the root directory.

#### Scenario: Running checks from root
- **WHEN** the developer executes `pnpm run lint` or `pnpm run test` or `pnpm run dev` at the root of the project
- **THEN** Turborepo executes the corresponding tasks across all workspace applications and packages in parallel
