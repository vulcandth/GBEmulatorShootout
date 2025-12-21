import json
import os
from time import gmtime, strftime
import re

current_time = gmtime()

emulators = json.load(open("emulators.json", "rt"))
tests = json.load(open("tests.json", "rt"))


def _format_tested_date(ts):
    if ts is None:
        return None
    try:
        return strftime("%Y-%m-%d", gmtime(float(ts)))
    except Exception:
        return None


def _make_safe_id(value, prefix="id"):
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value)).strip("-").lower()
    if not safe:
        safe = "item"
    return f"{prefix}-{safe}"

for name in emulators:
    if os.path.exists(emulators[name]['file']):
        data = json.load(open(emulators[name]['file'], "rt"))
        emulators[name].update(data)
        emulators[name]['passed'] = len([result for result in data['tests'].values() if result['result'] != "FAIL"])
        # Prefer the timestamp recorded in the results JSON, otherwise fall back
        # to the file modified time.
        tested_ts = data.get('date')
        if tested_ts is None:
            tested_ts = os.path.getmtime(emulators[name]['file'])
        emulators[name]['tested'] = tested_ts
        emulators[name]['tested_str'] = _format_tested_date(tested_ts)
    else:
        emulators[name].update({'passed': 0, 'tests': {}})
        emulators[name]['tested'] = None
        emulators[name]['tested_str'] = None

sorted_emulators = sorted(emulators.items(), key=lambda n: -n[1]['passed'])

f = open("index.html", "wt", encoding="utf-8", newline="\n")
f.write("""<!doctype html>
<html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>GB Emulator Shootout</title>
        <style>
            :root {
                --bg: #ffffff;
                --surface: #f7f7f8;
                --surface-2: #ffffff;
                --text: #111827;
                --muted: #6b7280;
                --border: #d1d5db;
                --border-strong: #9ca3af;
                --shadow: 0 8px 30px rgba(0, 0, 0, 0.08);

                --pass: #b8f5a8;
                --fail: #ffb3b3;
                --unknown: #ffe49b;
            }

            @media (prefers-color-scheme: dark) {
                :root {
                    --bg: #0b1020;
                    --surface: #0f172a;
                    --surface-2: #111b33;
                    --text: #e5e7eb;
                    --muted: #9ca3af;
                    --border: #22304d;
                    --border-strong: #33415f;
                    --shadow: 0 10px 30px rgba(0, 0, 0, 0.35);

                    --pass: #1f6f3a;
                    --fail: #7f1d1d;
                    --unknown: #7a5d14;
                }
            }

            * { box-sizing: border-box; }
            html, body { height: 100%; }
            body {
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: radial-gradient(1200px 400px at 50% 0%, rgba(99, 102, 241, 0.08), transparent 60%), var(--bg);
                color: var(--text);
            }

            a { color: inherit; text-decoration: none; }
            a:hover { text-decoration: underline; }

            .page {
                width: 100%;
                max-width: none;
                margin: 0 auto;
                padding: 24px 16px 40px;
            }

            header {
                display: flex;
                flex-direction: column;
                gap: 6px;
                margin-bottom: 16px;
            }
            header h1 {
                margin: 0;
                font-size: 20px;
                letter-spacing: 0.2px;
            }
            header p {
                margin: 0;
                color: var(--muted);
                font-size: 13px;
            }

            .header-row {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                gap: 12px;
                flex-wrap: wrap;
            }
            .header-right {
                display: flex;
                align-items: center;
                gap: 12px;
                justify-content: flex-end;
                flex-wrap: wrap;
            }

            .table-shell {
                background: var(--surface);
                border: 1px solid var(--border);
                border-radius: 14px;
                box-shadow: var(--shadow);
                overflow: hidden;
            }
            .table-wrap {
                overflow: auto;
                -webkit-overflow-scrolling: touch;
                max-height: calc(100vh - 160px);
            }

            table {
                border-collapse: separate;
                border-spacing: 0;
                width: max-content;
                min-width: 100%;
                background: var(--surface-2);
            }

            th, td {
                border-right: 1px solid var(--border);
                border-bottom: 1px solid var(--border);
                padding: 8px 10px;
                text-align: center;
                vertical-align: top;
                line-height: 1.25;
                font-size: 12px;
                white-space: nowrap;
            }

            thead th {
                position: sticky;
                top: 0;
                z-index: 3;
                background: color-mix(in srgb, var(--surface) 75%, transparent);
                backdrop-filter: blur(10px);
                border-bottom: 1px solid var(--border-strong);
            }

            th:first-child, td:first-child {
                position: sticky;
                left: 0;
                z-index: 2;
                text-align: right;
                background: var(--surface);
                border-right: 1px solid var(--border-strong);
            }
            thead th:first-child {
                z-index: 4;
            }

            .emu-title {
                display: block;
                font-weight: 600;
                font-size: 13px;
            }
            .emu-meta {
                display: block;
                margin-top: 4px;
                color: var(--muted);
                font-size: 11px;
            }

            .col-filter-label {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                margin: 8px auto 0;
                font-size: 11px;
                line-height: 1.2;
                color: var(--muted);
                white-space: nowrap;
            }
            .col-filter {
                font-size: 11px;
                line-height: 1.2;
                padding: 5px 8px;
                border: 1px solid var(--border);
                background: var(--surface-2);
                color: var(--text);
                border-radius: 10px;
                max-width: 160px;
            }
            .col-filter:focus {
                outline: 2px solid color-mix(in srgb, var(--border-strong) 70%, transparent);
                outline-offset: 2px;
            }

            .PASS { background: var(--pass); }
            .FAIL { background: var(--fail); }
            .UNKNOWN { background: var(--unknown); }
            .INFO { background: transparent; }

            .screenshot {
                width: 160px;
                height: 144px;
                display: block;
                margin: 6px auto 0;
                border-radius: 0;
                border: 1px solid var(--border);
                background: var(--surface-2);
            }

            .test {
                min-width: 140px;
                max-width: 220px;
            }
            th.test {
                white-space: normal;
                overflow-wrap: anywhere;
                word-break: break-word;
            }
            .test a {
                font-weight: 600;
                color: var(--muted);
                text-decoration: underline;
                text-underline-offset: 2px;
            }
            .test a:hover { color: var(--text); }

            .info-btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 18px;
                height: 18px;
                margin-left: 6px;
                border-radius: 999px;
                border: 1px solid var(--border);
                background: var(--surface-2);
                color: var(--muted);
                font-size: 12px;
                line-height: 1;
                cursor: pointer;
                vertical-align: middle;
            }
            .info-btn:hover { color: var(--text); }
            .info-popover {
                max-width: 320px;
                position: fixed;
                inset: auto;
                border: 1px solid var(--border);
                border-radius: 12px;
                background: var(--surface-2);
                color: var(--text);
                padding: 10px 12px;
                box-shadow: var(--shadow);
            }
        </style>
    </head>
    <body>
        <main class=\"page\">
            <header>
                <div class=\"header-row\">
                    <h1>GB Emulator Shootout</h1>
                    <div class=\"header-right\">
                        <p>Last site update: """ + strftime("%Y-%m-%d %H:%M", current_time) + """</p>
                    </div>
                </div>
            </header>

            <section class=\"table-shell\">
                <div class=\"table-wrap\">
                    <table>
                        <thead>
                            <tr>
                                <th style=\"text-align:left\">Updated On<br><span class=\"emu-meta\">""" + strftime("%Y-%m-%d", current_time) + """</span><span class=\"emu-meta\">Tests: <span id=\"rowCount\">""" + str(len(tests)) + """</span></span></th>
""")
for col_index, (name, emulator) in enumerate(sorted_emulators, start=2):
    tested = emulator.get('tested_str')
    tested_part = ("Tested %s" % tested) if tested else "Tested &mdash;"
    f.write(
        "                <th class='emulator'>"
        "<span class='emu-title'><a href=\"%s\">%s</a></span>"
        "<span class='emu-meta'>%d/%d &nbsp;&middot;&nbsp; %s</span>"
        "<label class=\"col-filter-label\">Filter: <select class=\"col-filter\" data-col=\"%d\" aria-label=\"Filter %s\">"
        "<option value=\"ALL\" selected>ALL</option>"
        "<option value=\"PASS\">PASS</option>"
        "<option value=\"FAIL\">FAIL</option>"
        "<option value=\"INFO\">INFO</option>"
        "<option value=\"NO_RESULT\">NO_RESULT</option>"
        "</select></label>"
        "</th>\n" % (emulator['url'], name, emulator['passed'], len(emulator['tests']), tested_part, col_index, name)
    )
f.write("              </tr>\n            </thead>\n            <tbody>\n")
for test_index, test in enumerate(tests):
    name = test['name'].replace("/", "/&#8203;")
    if test['url']:
        name = "<a href=\"%s\">%s</a>" % (test['url'], name)
    if test['description']:
        pop_id = _make_safe_id(f"{test_index}-{test['name']}", prefix="testinfo")
        name += (
            "<button type=\"button\" class=\"info-btn\" popovertarget=\"%s\" aria-label=\"Show test info\">i</button>"
            "<div id=\"%s\" class=\"info-popover\" popover>%s</div>" % (pop_id, pop_id, test['description'])
        )
    f.write("<tr><th class='test'>%s</th>\n" % (name))
    for name, emulator in sorted_emulators:
        result = emulator['tests'].get(test['name'])
        if result:
            f.write("  <td class='%s'>%s<br><img class='screenshot' src='data:image/png;base64,%s'></td>\n" % (result['result'], result['result'], result['screenshot']))
        else:
            f.write("  <td class='NO_RESULT'>No result</td>\n")
    f.write("</tr>\n")
f.write("""            </tbody>
                    </table>
                </div>
            </section>
        </main>

        <script>
            (function () {
                const selects = Array.from(document.querySelectorAll('.col-filter'));
                const rows = Array.from(document.querySelectorAll('tbody tr'));
                const rowCount = document.getElementById('rowCount');

                function updateRowCount() {
                    if (!rowCount) return;
                    rowCount.textContent = String(rows.filter(r => !r.hidden).length);
                }

                // Position Popover tooltips near the clicked info button.
                // (Popover API has limited anchoring support across browsers.)
                let openPopover = null;
                function clamp(value, min, max) {
                    return Math.min(Math.max(value, min), max);
                }
                function showPopoverNearButton(button) {
                    const targetId = button.getAttribute('popovertarget');
                    if (!targetId) return;
                    const pop = document.getElementById(targetId);
                    if (!pop) return;

                    if (openPopover && openPopover !== pop) {
                        try { openPopover.hidePopover(); } catch (e) {}
                    }

                    // Ensure it has an approximate size before positioning.
                    // We'll temporarily show it offscreen if needed.
                    let wasOpen = false;
                    try {
                        wasOpen = pop.matches(':popover-open');
                    } catch (e) {
                        // Some browsers may not support :popover-open; ignore.
                    }

                    if (!wasOpen) {
                        try {
                            pop.style.left = '-10000px';
                            pop.style.top = '-10000px';
                            pop.showPopover();
                        } catch (e) {
                            return;
                        }
                    }

                    const btnRect = button.getBoundingClientRect();
                    const popRect = pop.getBoundingClientRect();
                    const gap = 8;

                    // Prefer to the right; if not enough room, place left.
                    let left = btnRect.right + gap;
                    if (left + popRect.width > window.innerWidth - gap) {
                        left = btnRect.left - gap - popRect.width;
                    }
                    // Align vertically centered on the button.
                    let top = btnRect.top + (btnRect.height / 2) - (popRect.height / 2);

                    left = clamp(left, gap, window.innerWidth - gap - popRect.width);
                    top = clamp(top, gap, window.innerHeight - gap - popRect.height);

                    pop.style.left = left + 'px';
                    pop.style.top = top + 'px';
                    openPopover = pop;
                }

                document.querySelectorAll('.info-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        showPopoverNearButton(btn);
                    });
                });

                document.addEventListener('click', (e) => {
                    if (!openPopover) return;
                    const target = e.target;
                    if (target && (openPopover.contains(target) || target.closest && target.closest('.info-btn'))) {
                        return;
                    }
                    try { openPopover.hidePopover(); } catch (err) {}
                    openPopover = null;
                });

                function applyFilter(activeSelect) {
                    const value = activeSelect.value;
                    if (value === 'ALL') {
                        rows.forEach(r => r.hidden = false);
                        updateRowCount();
                        return;
                    }

                    const col = parseInt(activeSelect.dataset.col, 10);
                    rows.forEach(row => {
                        const cell = row.children[col - 1];
                        if (!cell) {
                            row.hidden = false;
                            return;
                        }

                        const cls = cell.classList;
                        let match = false;
                        if (value === 'NO_RESULT') {
                            match = cls.contains('NO_RESULT') || cell.textContent.trim() === 'No result';
                        } else if (value === 'INFO') {
                            // Treat UNKNOWN as part of INFO for filtering.
                            match = cls.contains('INFO') || cls.contains('UNKNOWN');
                        } else {
                            match = cls.contains(value);
                        }
                        row.hidden = !match;
                    });

                    updateRowCount();
                }

                selects.forEach(sel => {
                    sel.addEventListener('change', () => {
                        if (sel.value !== 'ALL') {
                            selects.forEach(other => {
                                if (other !== sel) other.value = 'ALL';
                            });
                        }

                        const active = selects.find(s => s.value !== 'ALL') || sel;
                        applyFilter(active);
                    });
                });

                updateRowCount();
            })();
        </script>
    </body>
</html>
""")
