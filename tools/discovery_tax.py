#!/usr/bin/env python3
"""
discovery_tax.py — measure the "Discovery Loop Tax".

Quantifies, on a *real* extracted book, how many tokens three strategies put
into an agent's context to answer one targeted question:

  1. context-dump   — the whole book stays resident, re-billed every turn
  2. discovery-loop — a live PDF-reading agent navigates: reads the ToC, then
                      pulls raw chapters until it locates the answer (and, per
                      Kyle Parratt's critique, backtracks for missing
                      definitions). These fetched pages land in history.
  3. book-to-skill  — a small resident SKILL.md core + one pre-compiled chapter
                      loaded on demand.

Honesty notes:
  * Token counts use tiktoken (cl100k_base) when installed, else a
    words/0.75 heuristic (the same constant the extractor uses). The method
    used is printed in the report.
  * The discovery-loop figure is a *model* with stated assumptions, not a
    measurement of a specific agent. It uses the REAL token sizes of the
    book's ToC and chapters, so it is a defensible estimate, not a guess.
  * It reports a best case (ToC + target chapter only) and a loop case
    (ToC + target chapter + one prior chapter for a missing definition).

Usage:
  python3 tools/discovery_tax.py --full-text <full_text.txt> \
      [--skill-dir <skill_folder>] [--target-chapter N] [--core-tokens 4000]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Reuse the extractor's hardened chapter detection instead of duplicating it, so
# discovery_tax and the pipeline always agree on what a chapter is (Arabic +
# Roman headings, prose/cross-reference rejection, list-item rejection).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from book_to_skill.utils import _chapter_number as chapter_number  # noqa: E402

TOC_RE = re.compile(r"^\s*(?:sum[áa]rio|table of contents|contents|[íi]ndice)\s*$",
                    re.IGNORECASE | re.MULTILINE)


def count_tokens(text: str) -> int:
    """Real BPE count via tiktoken if available; else words/0.75 heuristic."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return int(len(text.split()) / 0.75)


def token_method() -> str:
    try:
        import tiktoken  # noqa: F401
        return "tiktoken cl100k_base (real BPE)"
    except Exception:
        return "words/0.75 heuristic (tiktoken not installed)"


def split_chapters(text: str) -> list[tuple[int | None, str, str]]:
    """Return [(number, heading, body)], one segment per heading occurrence.

    The text before the first heading is the leading 'front matter / ToC'
    segment (number=None). A chapter number may appear more than once — a ToC
    entry and the real body share a heading format — so callers should pick the
    LARGEST-body occurrence as the real chapter (see best_chapter)."""
    lines = text.splitlines()
    segments: list[tuple[int | None, str, list[str]]] = [(None, "__front__", [])]
    for line in lines:
        num = chapter_number(line)
        if num is not None:
            segments.append((num, line.strip(), []))
        segments[-1][2].append(line)
    return [(n, h, "\n".join(b)) for n, h, b in segments]


def best_chapter(chapters: list[tuple[int | None, str, str]], n: int,
                 tok) -> tuple[str, int] | None:
    """Return (heading, body_tokens) for chapter number `n`, choosing the
    occurrence with the largest body — the real chapter, not a ToC line."""
    cands = [(h, tok(b)) for num, h, b in chapters if num == n]
    return max(cands, key=lambda x: x[1]) if cands else None


def extract_toc(front_matter: str) -> str:
    """Best-effort slice of the ToC block from the front matter."""
    m = TOC_RE.search(front_matter)
    if not m:
        # No explicit ToC: assume the agent skims the whole front matter.
        return front_matter
    # ToC runs from its heading to the end of the front matter.
    return front_matter[m.start():]


def generate_html_report(output_path: str, data: dict) -> None:
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token Tax Dashboard - {data['filename']}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://code.highcharts.com/11.4.8/highcharts.js"></script>
    <script src="https://code.highcharts.com/11.4.8/modules/exporting.js"></script>
    <script src="https://code.highcharts.com/11.4.8/modules/accessibility.js"></script>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 30, 49, 0.7);
            --border-color: rgba(75, 85, 99, 0.2);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-cyan: #06b6d4;
            --accent-purple: #8b5cf6;
            --accent-rose: #f43f5e;
            --accent-green: #10b981;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            line-height: 1.5;
        }}

        .dashboard-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(to right, #06b6d4, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .meta-subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }}

        .meta-badge-container {{
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}

        .meta-badge {{
            background: rgba(31, 41, 55, 0.6);
            border: 1px solid var(--border-color);
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        
        .meta-badge strong {{
            color: var(--text-primary);
        }}

        /* Metrics grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .metric-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .metric-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
        }}

        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
        }}

        .card-cyan::before {{ background: var(--accent-cyan); }}
        .card-purple::before {{ background: var(--accent-purple); }}
        .card-rose::before {{ background: var(--accent-rose); }}

        .metric-title {{
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}

        .metric-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            display: flex;
            align-items: baseline;
            gap: 0.5rem;
        }}

        .metric-value-cyan {{ color: var(--accent-cyan); }}
        .metric-value-purple {{ color: var(--accent-purple); }}
        .metric-value-rose {{ color: var(--accent-rose); }}

        .metric-subtext {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}

        /* Main layout grid */
        .layout-grid {{
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .chart-box {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
        }}

        .col-8 {{ grid-column: span 8; }}
        .col-4 {{ grid-column: span 4; }}
        .col-12 {{ grid-column: span 12; }}

        @media (max-width: 968px) {{
            .col-8, .col-4 {{
                grid-column: span 12;
            }}
        }}

        .chart-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
            color: var(--text-primary);
        }}

        /* Simulator controls */
        .simulator-container {{
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            height: 100%;
            justify-content: flex-start;
            padding-top: 0.5rem;
        }}

        .sim-slider-group {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}

        .sim-label-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.95rem;
        }}

        .sim-value {{
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            color: var(--accent-cyan);
        }}

        input[type="range"] {{
            -webkit-appearance: none;
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            outline: none;
        }}

        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: var(--accent-cyan);
            cursor: pointer;
            box-shadow: 0 0 10px rgba(6, 182, 212, 0.5);
            transition: background 0.15s;
        }}

        input[type="range"]::-webkit-slider-thumb:hover {{
            background: #22d3ee;
        }}

        .sim-metrics {{
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}

        .sim-metric-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            align-items: center;
            min-height: 2rem;
        }}

        .sim-metric-val {{
            font-weight: 600;
        }}

        .text-green {{ color: var(--accent-green); }}
        .text-rose {{ color: var(--accent-rose); }}

        footer {{
            margin-top: 3rem;
            border-top: 1px solid var(--border-color);
            padding-top: 1.5rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>

<div class="dashboard-container">
    <header>
        <div>
            <h1>Token Tax Dashboard</h1>
            <div class="meta-subtitle">Context usage simulation for book-to-skill efficiency</div>
        </div>
        <div class="meta-badge-container">
            <div class="meta-badge">Source: <strong>{data['filename']}</strong></div>
            <div class="meta-badge">Chapters: <strong>{data['chapters_count']}</strong></div>
            <div class="meta-badge">Target: <strong>Ch {data['target_chapter_num']}</strong></div>
            <div class="meta-badge">BPE: <strong>{data['token_method']}</strong></div>
        </div>
    </header>

    <!-- Metrics Cards Grid -->
    <div class="metrics-grid">
        <div class="metric-card card-cyan">
            <div class="metric-title">B2S vs Context Dump</div>
            <div class="metric-value metric-value-cyan">
                {round(data['dump_tokens'] / data['skill_tokens'], 1)}x
            </div>
            <div class="metric-subtext">Fewer tokens entering context per question</div>
        </div>
        <div class="metric-card card-purple">
            <div class="metric-title">B2S vs Discovery (Loop)</div>
            <div class="metric-value metric-value-purple">
                {round(data['disc_loop_tokens'] / data['skill_tokens'], 1)}x
            </div>
            <div class="metric-subtext">Fewer tokens than navigating ToC + Prior Chapter</div>
        </div>
        <div class="metric-card card-rose">
            <div class="metric-title">Dump Token Re-bill</div>
            <div class="metric-value metric-value-rose">
                {data['dump_tokens']:,}
            </div>
            <div class="metric-subtext">Tokens charged <strong>every single turn</strong></div>
        </div>
    </div>

    <!-- Layout Grid -->
    <div class="layout-grid">
        <!-- Single Question Token Cost Comparison -->
        <div class="chart-box col-8">
            <div id="costChart" style="width: 100%; height: 350px;"></div>
        </div>

        <!-- Simulator Form -->
        <div class="chart-box col-4">
            <div class="chart-title">Turn Calculator</div>
            <div class="simulator-container">
                <div class="sim-slider-group">
                    <div class="sim-label-row">
                        <span>Conversation Length:</span>
                        <span class="sim-value" id="turnVal">5 turns</span>
                    </div>
                    <input type="range" id="turnSlider" min="1" max="20" value="5">
                </div>

                <div class="sim-metrics">
                    <div class="sim-metric-row">
                        <span>Context Dump Cost:</span>
                        <span class="sim-metric-val" id="dumpCostVal">0 tokens</span>
                    </div>
                    <div class="sim-metric-row">
                        <span>Book-to-Skill Cost:</span>
                        <span class="sim-metric-val" id="b2sCostVal">0 tokens</span>
                    </div>
                    <div class="sim-metric-row" style="border-top: 1px solid var(--border-color); padding-top: 0.5rem; font-weight: 600;">
                        <span>Total Savings:</span>
                        <span class="sim-metric-val text-green" id="savingsVal">0 tokens</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Cumulative Cost Progression Graph -->
        <div class="chart-box col-12">
            <div id="cumulativeChart" style="width: 100%; height: 380px;"></div>
        </div>
    </div>

    <footer>
        <p>Generated by book-to-skill CLI • Open Agent Skills standard • cost calculations based on actual BPE token size of {data['filename']}</p>
    </footer>
</div>

<script>
    // 1. Injected Token Data
    const tokenData = {{
        dump: {data['dump_tokens']},
        disc_best: {data['disc_best_tokens']},
        disc_loop: {data['disc_loop_tokens']},
        skill: {data['skill_tokens']}
    }};

    // 2. Simulator Interactive Logic (Run first to ensure functionality even if Highcharts is blocked)
    const turnSlider = document.getElementById('turnSlider');
    const turnVal = document.getElementById('turnVal');
    const dumpCostVal = document.getElementById('dumpCostVal');
    const b2sCostVal = document.getElementById('b2sCostVal');
    const savingsVal = document.getElementById('savingsVal');

    function updateSimulation() {{
        const turns = parseInt(turnSlider.value);
        turnVal.textContent = turns === 1 ? '1 turn' : turns + ' turns';
        
        const dumpCost = tokenData.dump * turns;
        const b2sCost = tokenData.skill * turns;
        const savings = dumpCost - b2sCost;
        
        dumpCostVal.textContent = dumpCost.toLocaleString() + ' tokens';
        b2sCostVal.textContent = b2sCost.toLocaleString() + ' tokens';
        
        if (savings >= 0) {{
            savingsVal.innerHTML = savings.toLocaleString() + ' tokens <span style="font-size: 0.75rem; opacity: 0.85; font-weight: normal; white-space: nowrap;">(' + Math.round(savings / dumpCost * 100) + '% saved)</span>';
            savingsVal.className = 'sim-metric-val text-green';
        }} else {{
            savingsVal.innerHTML = Math.abs(savings).toLocaleString() + ' tokens <span style="font-size: 0.75rem; opacity: 0.85; font-weight: normal; white-space: nowrap;">(' + Math.round(Math.abs(savings) / dumpCost * 100) + ' extra)</span>';
            savingsVal.className = 'sim-metric-val text-rose';
        }}
    }}

    if (turnSlider) {{
        turnSlider.addEventListener('input', updateSimulation);
        updateSimulation();
    }}

    // 3. Render Highcharts Charts (Wrapped in safety checks to prevent page crash if offline)
    if (typeof Highcharts !== 'undefined') {{
        try {{
            // Setup Highcharts global theme
            Highcharts.setOptions({{
                chart: {{
                    backgroundColor: 'transparent',
                    style: {{
                        fontFamily: "'Inter', sans-serif"
                    }}
                }},
                title: {{
                    style: {{
                        color: '#f3f4f6',
                        fontFamily: "'Outfit', sans-serif",
                        fontWeight: '600',
                        fontSize: '1.25rem'
                    }}
                }},
                credits: {{ enabled: false }},
                exporting: {{ enabled: false }}
            }});

            // Render single-turn cost chart
            Highcharts.chart('costChart', {{
                chart: {{
                    type: 'column',
                    spacingTop: 10
                }},
                title: {{
                    text: 'Tokens Entering Context (Single Question)',
                    align: 'left'
                }},
                xAxis: {{
                    categories: ['Context Dump', 'Discovery (Best)', 'Discovery (Loop)', 'Book-to-Skill'],
                    labels: {{
                        style: {{ color: '#9ca3af', fontWeight: '500' }}
                    }},
                    lineColor: 'rgba(75, 85, 99, 0.3)'
                }},
                yAxis: {{
                    title: {{
                        text: 'Tokens',
                        style: {{ color: '#9ca3af' }}
                    }},
                    gridLineColor: 'rgba(75, 85, 99, 0.1)',
                    labels: {{
                        style: {{ color: '#9ca3af' }}
                    }}
                }},
                tooltip: {{
                    shared: true,
                    backgroundColor: '#111827',
                    borderColor: '#374151',
                    style: {{ color: '#f3f4f6' }},
                    valueSuffix: ' tokens'
                }},
                plotOptions: {{
                    column: {{
                        borderRadius: 5,
                        colorByPoint: true,
                        colors: ['#6b7280', '#3b82f6', '#8b5cf6', '#06b6d4'],
                        borderWidth: 0,
                        dataLabels: {{
                            enabled: true,
                            color: '#f3f4f6',
                            style: {{ fontSize: '0.85rem', textOutline: 'none' }},
                            formatter: function() {{
                                return this.y.toLocaleString();
                            }}
                        }}
                    }}
                }},
                series: [{{
                    name: 'Token Cost',
                    data: [tokenData.dump, tokenData.disc_best, tokenData.disc_loop, tokenData.skill],
                    showInLegend: false
                }}]
            }});

            // Render Cumulative Cost Progression Chart
            Highcharts.chart('cumulativeChart', {{
                chart: {{
                    type: 'area',
                    spacingTop: 15
                }},
                title: {{
                    text: 'Cumulative Token Intake over Chat turns',
                    align: 'left'
                }},
                xAxis: {{
                    categories: Array.from({{length: 10}}, (_, i) => 'Turn ' + (i + 1)),
                    labels: {{
                        style: {{ color: '#9ca3af' }}
                    }},
                    lineColor: 'rgba(75, 85, 99, 0.3)'
                }},
                yAxis: {{
                    title: {{
                        text: 'Cumulative Tokens',
                        style: {{ color: '#9ca3af' }}
                    }},
                    gridLineColor: 'rgba(75, 85, 99, 0.1)',
                    labels: {{
                        style: {{ color: '#9ca3af' }}
                    }}
                }},
                tooltip: {{
                    shared: true,
                    backgroundColor: '#111827',
                    borderColor: '#374151',
                    style: {{ color: '#f3f4f6' }}
                }},
                plotOptions: {{
                    area: {{
                        marker: {{
                            enabled: false,
                            symbol: 'circle',
                            radius: 2,
                            states: {{
                                hover: {{ enabled: true }}
                            }}
                        }},
                        fillOpacity: 0.15,
                        lineWidth: 2
                    }}
                }},
                series: [
                    {{
                        name: 'Context Dump (Fully Resident)',
                        data: Array.from({{length: 10}}, (_, i) => tokenData.dump * (i + 1)),
                        color: '#f43f5e'
                    }},
                    {{
                        name: 'Discovery Loop (Average Load)',
                        data: Array.from({{length: 10}}, (_, i) => tokenData.disc_loop + (tokenData.disc_loop * 0.15 * i)),
                        color: '#8b5cf6'
                    }},
                    {{
                        name: 'Book-to-Skill (Resident Core + Demand Chapter)',
                        data: Array.from({{length: 10}}, (_, i) => tokenData.skill * (i + 1)),
                        color: '#06b6d4'
                    }}
                ]
            }});
        }} catch (err) {{
            console.error("Error initializing Highcharts graphs:", err);
        }}
    }} else {{
        const fallbackHTML = (title, height) => `
            <div style="display: flex; height: ${{height}}px; align-items: center; justify-content: center; color: #9ca3af; text-align: center; padding: 2rem; border: 1px dashed rgba(75, 85, 99, 0.3); border-radius: 0.75rem; background: rgba(17, 24, 39, 0.2);">
                <div>
                    <span style="font-size: 2rem; display: block; margin-bottom: 0.5rem;">📊</span>
                    <h3 style="font-family: 'Outfit', sans-serif; font-size: 1.1rem; font-weight: 600; color: #f3f4f6; margin-bottom: 0.25rem;">${{title}}</h3>
                    <p style="font-size: 0.85rem; color: #9ca3af; max-width: 320px; margin: 0 auto 0.5rem;">Highcharts library could not be loaded from CDN.</p>
                    <p style="font-size: 0.75rem; color: #6b7280; max-width: 300px; margin: 0 auto;">Check your internet connection or browser security settings to view the interactive charts.</p>
                </div>
            </div>`;
        document.getElementById('costChart').innerHTML = fallbackHTML('Tokens Entering Context (Single Question)', 350);
        document.getElementById('cumulativeChart').innerHTML = fallbackHTML('Cumulative Token Intake over Chat turns', 380);
    }}
</script>
</body>
</html>
"""
    temp_file = Path(output_path).with_suffix(".tmp")
    try:
        temp_file.write_text(html_content, encoding="utf-8")
        temp_file.replace(output_path)
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        raise e


def main() -> int:
    ap = argparse.ArgumentParser(description="Measure the Discovery Loop Tax on a real book.")
    ap.add_argument("--full-text", required=True, help="extractor full_text.txt")
    ap.add_argument("--skill-dir", help="generated skill folder (for SKILL.md + chapter sizes)")
    ap.add_argument("--target-chapter", type=int, default=5,
                    help="1-based chapter index the question is about")
    ap.add_argument("--core-tokens", type=int, default=4000,
                    help="resident SKILL.md core size if --skill-dir not given (design cap)")
    ap.add_argument("--html", help="output path for the visual token tax HTML report")
    args = ap.parse_args()

    full_text = Path(args.full_text).read_text(encoding="utf-8", errors="ignore")
    total = count_tokens(full_text)

    segs = split_chapters(full_text)
    front = segs[0][2]
    chapters = segs[1:]  # [(number, heading, body)]
    if not chapters:
        print("No chapters detected — cannot model discovery. The source may be a\n"
              "technical PDF whose headings were flattened by text extraction; try\n"
              "technical mode (Docling) so chapter structure is preserved.", file=sys.stderr)
        return 1

    toc = extract_toc(front)
    toc_tok = count_tokens(toc)

    # Distinct chapter numbers present (a number can recur: ToC entry + body).
    distinct = sorted({num for num, _, _ in chapters if num is not None})

    # Select the target by chapter NUMBER, taking the largest-body occurrence so
    # a ToC line isn't mistaken for the chapter. Fall back to positional.
    n = args.target_chapter
    best = best_chapter(chapters, n, count_tokens)
    if best is None:
        n = distinct[min(n - 1, len(distinct) - 1)] if distinct else n
        best = best_chapter(chapters, n, count_tokens)
    target_heading, target_raw = best
    prior = best_chapter(chapters, n - 1, count_tokens)
    prior_raw = prior[1] if prior else 0

    # book-to-skill resident cost
    if args.skill_dir:
        sd = Path(args.skill_dir)
        skill_md = sd / "SKILL.md"
        core = count_tokens(skill_md.read_text(encoding="utf-8")) if skill_md.exists() else args.core_tokens
        chs = sorted((sd / "chapters").glob("*.md")) if (sd / "chapters").is_dir() else []
        # use the target chapter file if present, else the average of generated chapters
        comp_chapter = None
        for c in chs:
            if re.search(rf"ch0*{n}\b", c.name):
                comp_chapter = count_tokens(c.read_text(encoding="utf-8"))
                break
        if comp_chapter is None and chs:
            comp_chapter = sum(count_tokens(c.read_text(encoding="utf-8")) for c in chs) // len(chs)
        comp_chapter = comp_chapter or 1000
        core_label = "measured SKILL.md" if skill_md.exists() else "design cap"
    else:
        core = args.core_tokens
        comp_chapter = 1000
        core_label = "design cap (no --skill-dir)"

    dump = total
    skill = core + comp_chapter
    disc_best = toc_tok + target_raw
    disc_loop = toc_tok + target_raw + prior_raw

    def ratio(a: int, b: int) -> str:
        return f"{a / b:.1f}x" if b else "n/a"

    print("Discovery Loop Tax — measured on a real book\n")
    print(f"  token method : {token_method()}")
    print(f"  source       : {Path(args.full_text).name}")
    print(f"  chapters      : {len(distinct)} detected")
    print(f"  target        : chapter {n}  ({target_heading[:60]})")
    print(f"  book total    : {total:,} tokens\n")

    print("  Cost to answer ONE targeted question (tokens entering context):\n")
    print(f"    context-dump      : {dump:>9,}   (resident, re-billed EVERY turn)")
    print(f"    discovery (best)  : {disc_best:>9,}   ToC ({toc_tok:,}) + raw target chapter ({target_raw:,})")
    print(f"    discovery (loop)  : {disc_loop:>9,}   + 1 prior chapter for a missing definition ({prior_raw:,})")
    print(f"    book-to-skill     : {skill:>9,}   core [{core_label}] ({core:,}) + compiled chapter ({comp_chapter:,})\n")

    print("  book-to-skill advantage:")
    print(f"    vs context-dump   : {ratio(dump, skill)} fewer tokens")
    print(f"    vs discovery best : {ratio(disc_best, skill)} fewer tokens")
    print(f"    vs discovery loop : {ratio(disc_loop, skill)} fewer tokens")
    print("\n  Note: the discovery figures are a model using the book's real ToC/chapter")
    print("  sizes; a single read, not a recurring cost. context-dump recurs every turn.")

    if args.html:
        html_data = {
            "filename": Path(args.full_text).name,
            "token_method": token_method(),
            "chapters_count": len(distinct),
            "target_chapter_num": n,
            "target_chapter_title": target_heading,
            "total_tokens": total,
            "dump_tokens": dump,
            "disc_best_tokens": disc_best,
            "disc_loop_tokens": disc_loop,
            "skill_tokens": skill,
            "toc_tokens": toc_tok,
            "target_chapter_tokens": target_raw,
            "prior_chapter_tokens": prior_raw,
            "core_tokens": core,
            "compiled_chapter_tokens": comp_chapter,
            "core_label": core_label
        }
        try:
            generate_html_report(args.html, html_data)
            print(f"\n  Visual Token Tax report generated: {args.html}")
        except Exception as e:
            print(f"\n  ERROR generating Visual Token Tax report: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
