# AI Development Notes

## AI tools used

- ChatGPT was used as an AI coding assistant for architecture decisions, implementation support, debugging, test design, and UI improvements.
- The application optionally supports an OpenAI model for natural-language intent classification.

## How AI was used

AI was used to help design a small, explainable architecture:

`Natural language question → intent classification → allowlisted SQL template → SQLite → supporting figures → UI`

The model is explicitly prevented from generating executable SQL. This keeps the database access deterministic and makes unsupported questions return a controlled response.

## Problems encountered and debugging

1. Natural-language wording varied widely (`top product`, `best product`, `most units`, `online vs retail`).
2. Initial keyword matching only supported the five examples from the challenge.
3. Entity-specific questions could be confused with generic breakdown questions.
4. Invalid dataset rows needed a consistent revenue policy.

These were addressed with a broader intent layer, explicit entity matching, ordered intent checks, and a documented revenue rule.

## Data-quality policy

The supplied dataset contains a returned transaction, a zero-quantity transaction, and a transaction with a missing unit price. These records remain stored for traceability. Revenue KPIs include only completed transactions with positive quantity and known unit price.

## What I would improve with another day

- Replace the lightweight rule-based fallback with a structured LLM router using confidence scores.
- Add more advanced date filters and natural-language date ranges.
- Add charts for category/channel/product comparisons.
- Add query history and export to CSV.
- Add Docker and CI/CD.
- Deploy on AWS using a managed database and containerized FastAPI service.
