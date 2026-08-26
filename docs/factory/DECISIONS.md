# Factory decisions

Why the factory is configured the way it is. Written by a human, informed by
`/factory-tune`.

This file exists so a future tuning pass can tell whether a past loosening was a mistake.
Without it, every constraint review starts from scratch and the same argument gets had
twice a year.

Newest at the top.

---

## Pilot decisions

### 2026-08-26 - One low-risk pilot before any expansion

**Change:** Install Factory only in the existing MiP shared-tool repository
`/Users/mipcoaching/MiP-OS/TOOLS/book-to-skill`; do not deploy it to sibling projects.

**Evidence:** The repository was clean, has a public origin, contains no authentication,
customer-data, financial-data, secrets, or deployment-control-plane implementation, and
its CI defines executable lint, test, smoke, documentation-build, security, and skill-
contract checks. The Factory upstream suite also passed at commit
`8af116567166a0a16588b7ab1b9934ece0b775bc`.

**Risk accepted:** The pilot adds repository-local agent instructions, hooks, and policy
files to a public OSS checkout. All factory and project contract paths are protected, no
auto-merge is allowed, and GitHub writes remain disabled until a human reviews them. The
initial pre-rebase bootstrap measured 2,387 inserted lines and is a one-time exception to
the charter's 400-line routine diff limit; later changes must remain focused and under it.

**Revisit if:** Any gate bypass, policy conflict, unexpected hook behavior, escaped defect,
or human review queue above three items is observed.

---

## Standing decisions

### 2026-08-16 - Merge is never automated, on any tier

**Change:** No routine or session may merge, on any tier including `revival`. Enforced by a
GitHub ruleset or branch protection. Harness hooks block common shell routes as a second
layer.

**Evidence:** Structural rather than empirical. The merge decision is where accountability
lives, and it is the one point where a human takes responsibility for consequences.

**Risk accepted:** Throughput is capped by human review availability. This is intentional.
The binding constraint on a factory is decisions pending judgment, not agents running.

**Revisit if:** Never, at any tier.

---

### 2026-08-16 - Verification is a separate agent from implementation

**Change:** `factory-implement` must delegate to the `factory-verifier` subagent and may
not self-certify.

**Evidence:** An agent asked to check its own work grades the intent it already had. The
separation is the only thing that makes a green result mean anything.

**Risk accepted:** Roughly doubles token cost per item. Worth it.

**Revisit if:** Never. Tune the verifier's strictness instead.

---

### 2026-08-16 - Unattended runs may not modify existing test files

**Change:** An unattended run stops before modifying a pre-existing test file. An
interactive session requires explicit human approval, stays draft, and receives a human
read regardless of gate status.

**Evidence:** Agents can rewrite assertions to match broken behavior. An unexplained green
suite after the implementation agent changed the tests is weak evidence and can be
invisible to ordinary automated checks because everything passes.

**Risk accepted:** Legitimate test refactors need a human. Acceptable.

**Revisit if:** Never, while the gates depend on the tests being trustworthy.
