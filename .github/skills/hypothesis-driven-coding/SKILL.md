---
name: hypothesis-driven-coding
description: 'Use when implementing, debugging, refactoring, or reviewing code in a repository. Route from a concrete anchor to the controlling code path, form a falsifiable local hypothesis, make the smallest testable change, and validate it with focused checks before widening scope.'
argument-hint: 'Describe the requested behavior, failing check, or code area to investigate.'
user-invocable: true
---

# Hypothesis-Driven Coding

## Purpose

Turn an ambiguous coding request into a small, evidence-driven change. Keep exploration local, preserve unrelated work, and finish with executable validation whenever the repository provides it.

## Procedure

1. **Find the concrete anchor.** Start from the named file, symbol, failing command, test, error, or nearby implementation. If none is named, perform one targeted search to locate it.
2. **Trace ownership locally.** Read only enough nearby code to find where the behavior is actually computed, mutated, or controlled. If the first file only forwards or registers behavior, take one nearby hop to its owner.
3. **State the working hypothesis.** Before editing, identify one falsifiable explanation for the current behavior and one cheap check that could disconfirm it. Prefer a neighboring test, call site, type check, or focused runtime command.
4. **Choose the smallest probe or fix.** Make one narrow, reversible edit that directly tests the hypothesis. Preserve existing public APIs and local conventions unless the request requires changing them. Do not reformat unrelated code.
5. **Validate immediately.** After the first substantive edit, run the cheapest behavior-scoped check available. Prefer, in order: the failing check, a focused test, a narrow compile/type/lint check, then a diff inspection only when no executable check exists.
6. **Interpret the result.**
   - If validation supports the hypothesis but reveals a local defect, repair the same slice and rerun the same check.
   - If validation falsifies the hypothesis, move one hop toward the code that more directly controls the behavior; do not restart broad exploration.
   - If validation is ambiguous, perform one nearby disambiguating read or call-site check, then decide whether to repair or move one hop.
7. **Complete adjacent work narrowly.** Apply only follow-up edits required by the validated change, rerunning focused validation after each meaningful slice.
8. **Run the security gate.** When the change touches input handling, authentication, authorization, secrets, file or network access, dependencies, serialization, or generated commands, check the relevant trust boundary. Reject unsafe defaults, validate untrusted input, use least privilege, avoid logging secrets, and preserve existing security controls. Run a focused security test, static check, dependency audit, or manual review when one is available.
9. **Check the final boundary.** Confirm the requested behavior, relevant tests or diagnostics, security implications, and any required documentation are handled. Inspect the final diff for accidental scope expansion. Never revert unrelated user changes or create commits unless explicitly requested.

## Decision Rules

- Prefer an existing helper, abstraction, test, and command over a new pattern.
- Treat user input, external responses, files, environment variables, tool output, and generated content as untrusted until validated.
- Do not print, commit, copy, or place secrets in source, logs, prompts, test fixtures, or command arguments. Ask the user to enter secrets directly into their terminal when required.
- For security-sensitive changes, verify authentication, authorization, access scope, injection resistance, safe error handling, and dependency or configuration impact before declaring completion.
- Treat repeated searching without a sharper hypothesis as drift; choose the best current local hypothesis and make a small probe.
- If no discriminating check exists, add the smallest observable check or use a narrow type/runtime validation before changing more code.
- Scale tests with risk: keep them focused for local changes and broaden them for shared contracts or user-facing workflows.
- Stop after three repair attempts in the same file if the issue remains unresolved; report the blocker and the evidence gathered.

## Completion Checklist

- [ ] The controlling code path was identified from a concrete anchor.
- [ ] A falsifiable hypothesis and discriminating check were established before the first edit.
- [ ] The change is minimal and consistent with local patterns.
- [ ] Focused executable validation ran after editing, or its absence is documented.
- [ ] Security-sensitive boundaries were checked, or the change was confirmed not to affect them.
- [ ] Any validation failure was addressed without widening scope unnecessarily.
- [ ] The final diff contains no unrelated changes.
- [ ] Remaining test gaps, assumptions, or blockers are stated clearly.
