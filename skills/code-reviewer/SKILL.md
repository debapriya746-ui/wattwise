---
name: code-reviewer
description: |
  Reviews every file written by Antigravity 
  before it is committed or used.
  Use after every new file is created.
  Use before any code runs.
  Do NOT skip this review for any file.
---

## Checklist
Run every check below on every file.
Return PASS or FAIL for each check.
If any check FAILS, stop and fix before 
moving to next file.

### Security Checks
1. No API keys or secrets hardcoded in any file
2. No exact GPS coordinates stored anywhere
3. No exact address stored anywhere
4. No personal identity data stored anywhere

### Agent Behavior Checks
5. Every agent returns structured JSON not free text
6. Every API call has a fallback defined
7. Every agent decision is logged
8. No agent assumes — always confirms with user
9. Verification step happens before calculation
10. Saving tips only run if user says YES

### Output Checks
11. Output always shows ranges not single number
12. Confidence level always shown in output
13. Rate source always shown in output
14. Disclaimer present in UI and README

### Structure Checks
15. File is in correct folder per project structure
16. File does not contain code not asked for
17. File matches the spec in specs/wattwise.md

### Code Quality Checks
18. No unused imports or variables
19. No hardcoded magic numbers
    (days=30 must be a named constant)
20. No bare except: clauses
    every error caught must be specific
21. No silent failures — all errors logged
22. API calls have timeout limit defined
23. No single function longer than 50 lines

### Data Validation Checks
24. Wattage input between 1W and 5000W
25. Hours input between 0 and 24
26. Rate input is positive non-zero number
27. Pincode format validated before API call
28. No calculation runs with zero appliances

### Session Privacy Checks
29. Session data cleared after session ends
30. No data leakage between user sessions

## Output Format
{
  "file_reviewed": "agents/calculator_agent.py",
  "checks_passed": 16,
  "checks_failed": 1,
  "failed_checks": [
    {
      "check": 1,
      "issue": "API key hardcoded on line 12",
      "fix": "Move to environment variable"
    }
  ],
  "overall": "FAIL",
  "action": "Fix failed checks before proceeding"
}

## Fallback
If file is empty or placeholder:
  → Skip review
  → Note: "Placeholder file, review when complete"
