---
name: frontend-design-project
description: Use when implementing frontend pages, layouts, routes, or reusable UI components for this repository after the design has been approved, especially when the work must follow the project's fixed React and Vite stack and frontend-backend separation rules.
---

# Frontend Design Project Companion

This skill is a project-specific companion to `frontend-design`.

Use it together with `frontend-design` when building frontend UI in this repository. Do not modify or replace the upstream `frontend-design` skill with project conventions. This skill exists to supply repository rules, stack constraints, and workflow gates.

## Scope

This skill applies only to frontend implementation work:
- pages
- layouts
- route structure
- reusable UI components
- client-side state presentation
- loading, empty, error, and success states
- frontend interaction behavior

Do not use this skill for:
- backend services
- API route implementation
- database design
- model or packet-evaluator logic
- infrastructure or deployment work

## Required Skill Pairing

When this skill is used for implementation, also use:
- `superpowers:brainstorming` first
- `frontend-design` for the actual visual and interaction implementation

Hard rule:
- Do not use `frontend-design` for this repository until the UI or feature design has been discussed and approved through `superpowers:brainstorming`.
- After design approval, use this skill to enforce repository constraints during implementation.

Recommended sequence:
1. `superpowers:brainstorming`
2. design approval
3. `frontend-design-project`
4. `frontend-design`

If a task is large enough to need implementation planning, continue with `superpowers:writing-plans` before coding.

## Fixed Frontend Stack

Frontend work in this repository must target this stack unless the user explicitly changes it:
- React
- TypeScript
- Vite
- React Router
- TanStack Query
- pnpm

Default expectations:
- use React function components
- use TypeScript throughout
- use Vite as the frontend app and build tool
- use React Router for route composition
- use TanStack Query for server-state fetching, caching, and async status handling
- use pnpm for package management and workspace commands

Do not introduce a different frontend stack by default:
- no Next.js
- no Remix
- no Vue
- no Angular
- no Redux unless the user explicitly asks for it

## Architecture Constraints

This project uses frontend-backend separation.

Frontend responsibilities:
- render pages and components
- collect user input
- call backend APIs over HTTP
- display backend results and task status
- manage client-side route state and request state

Backend responsibilities:
- file upload handling
- packet generation
- model invocation
- evaluation task status management
- artifact persistence

Do not move backend concerns into the frontend unless the user explicitly changes the architecture.

## Implementation Rules

Frontend implementations should follow these rules:
- Prefer clear separation between route-level code, shared UI components, and API client logic.
- Keep API calling code out of presentation-only components.
- Model all remote requests with explicit loading, empty, error, and success states.
- Build mobile-first and preserve usability on desktop.
- Keep visual ambition high, but do not trade away readability, accessibility, or maintainability.
- Reuse shared styling tokens and layout conventions once they exist.
- Avoid one-off component abstractions unless they clearly reduce duplication or improve clarity.

## Default Frontend Boundaries

Assume these screens will exist unless the user narrows scope:
- upload page
- evaluation detail page
- history page

Assume these frontend integration points will exist unless the backend design changes:
- create evaluation
- read evaluation status
- read final report
- read packet artifact

## Quality Bar

Every frontend implementation should be:
- production-oriented, not demo-only
- responsive
- accessible enough for normal keyboard and screen-size usage
- explicit about async state
- visually intentional rather than generic
- easy to extend when backend APIs evolve

## Common Mistakes

Avoid these repository-specific failures:
- using `frontend-design` before `brainstorming` approval
- treating the frontend as a full-stack framework app
- coupling UI components directly to ad hoc fetch calls everywhere
- skipping error and empty states because mock data looks complete
- choosing flashy visuals that reduce information density or task clarity
- adding framework dependencies that conflict with the fixed stack
