name: CodeQL

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
  schedule:
    # Weekly scan so newly-disclosed query packs catch latent issues.
    - cron: "27 4 * * 1"

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    name: analyze (python)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v4
        with:
          languages: python
          queries: security-and-quality
      - name: Perform CodeQL analysis
        uses: github/codeql-action/analyze@v4
        with:
          category: "/language:python"
