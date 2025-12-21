import json
import os
import re
import time

# Get the time before doing anything else
last_site_update = time.strftime("%Y-%m-%d %H:%M %Z", time.gmtime())

# Load the data from JSON
emulators = json.load(open("emulators.json", "rt"))
tests = json.load(open("tests.json", "rt"))

for name in emulators:
    if os.path.exists(emulators[name]['file']):
        data = json.load(open(emulators[name]['file'], "rt"))
        emulators[name].update(data)
        emulators[name]['passed'] = len([result for result in data['tests'].values() if result['result'] != "FAIL"])
        # Prefer the timestamp recorded in the results JSON, otherwise fall back to the file modified time
        tested_ts = data.get('date') or os.path.getmtime(emulators[name]['file'])
        emulators[name]['tested'] = tested_ts
        try:
            emulators[name]['tested_str'] = time.strftime("%Y-%m-%d", time.gmtime(float(tested_ts)))
        except:
            emulators[name]['tested_str'] = None
    else:
        emulators[name].update({'passed': 0, 'tests': {}})
        emulators[name]['tested'] = None
        emulators[name]['tested_str'] = None

# Sort by the number of tests passed from highest to lowest, then by emulator name alphabetically
emulators = dict(sorted(emulators.items(), key=lambda item: (-item[1]['passed'], item[0])))

file = open("index.html", "wt", encoding="utf-8", newline="\n")
file.write("""<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
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

            * {
                box-sizing: border-box;
            }
            html, body {
                height: 100%;
            }
            body {
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: radial-gradient(1200px 400px at 50% 0%, rgba(99, 102, 241, 0.08), transparent 60%), var(--bg);
                color: var(--text);
            }

            a:link, a:visited {
                color: inherit;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }

            .page {
                width: 100%;
                height: 100%;
                margin: 0;
                padding: 16px;
                display: flex;
                flex-direction: column;
            }

            header {
                display: flex;
                flex-direction: row;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
                flex-wrap: wrap;
                margin-bottom: 16px;
            }
            header h1 {
                margin: 0;
                font-size: 20px;
                letter-spacing: 0.2px;
            }
            header aside {
                color: var(--muted);
                font-size: 13px;
            }
            header aside a:link {
                text-decoration: underline;
            }

            .table-wrap {
                background: var(--surface);
                border: 1px solid var(--border);
                box-shadow: var(--shadow);
                overflow: auto;
                -webkit-overflow-scrolling: touch;
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
                line-height: 16px;
                font-size: 12px;
                white-space: nowrap;
            }

            thead th {
                position: sticky;
                top: 0;
                z-index: 3;
                background: color-mix(in srgb, var(--surface) 85%, transparent);
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
                color: var(--muted);
                font-size: 11px;
                line-height: 16px;
            }

            .col-filter-label {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                margin: 8px auto 0;
                font-size: 11px;
                line-height: 16px;
                color: var(--muted);
                white-space: nowrap;
            }
            .col-filter {
                font-size: 11px;
                line-height: 16px;
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
            .test a:link, .test a:visited, .test a:hover {
                font-weight: 600;
                color: var(--text);
                text-decoration: underline;
                text-underline-offset: 2px;
            }

            .info-btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 16px;
                height: 16px;
                margin-left: 6px;
                border-radius: 8px;
                border: 1px solid var(--border);
                background: var(--surface-2);
                color: var(--muted);
                font-size: 11px;
                line-height: 16px;
                cursor: pointer;
                vertical-align: middle;
            }
            .info-btn:hover {
                color: var(--text);
            }
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
        <main class="page">
            <header>
                <h1>
                    <a href="https://vulcandth.github.io/GBEmulatorShootout/">GB Emulator Shootout</a>
                </h1>
                <aside>
                    <a href="https://github.com/vulcandth/GBEmulatorShootout">GitHub</a>
                    &middot;
                    Last site update: """ + last_site_update + """
                </aside>
            </header>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th style="text-align:left">
                                Tests: <span id="rowCount" class="emu-meta">""" + str(len(tests)) + """</span>
                            </th>
""")

for col_index, (name, emulator) in enumerate(emulators.items(), start=2):
    tested = emulator.get('tested_str')
    tested_part = ("Tested %s" % tested) if tested else "Tested &mdash;"
    file.write(
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

file.write("""
                        </tr>
                    </thead>
                    <tbody>
""")

for test_index, test in enumerate(tests):
    name = test['name'].replace("/", "/&#8203;")
    if test['url']:
        name = "<a href=\"%s\">%s</a>" % (test['url'], name)
    if test['description']:
        test_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", test['name']).strip("-").lower() or "item"
        pop_id = "testinfo-%d-%s" % (test_index, test_name)
        name += (
            "<button type=\"button\" class=\"info-btn\" popovertarget=\"%s\" aria-label=\"Show test info\">i</button>"
            "<div id=\"%s\" class=\"info-popover\" popover>%s</div>" % (pop_id, pop_id, test['description'])
        )
    file.write("<tr><th class='test'>%s</th>\n" % (name,))
    for name, emulator in emulators.items():
        result = emulator['tests'].get(test['name'])
        if result:
            file.write("  <td class='%s'>%s<br><img class='screenshot' src='data:image/png;base64,%s'></td>\n" % (result['result'], result['result'], result['screenshot']))
        else:
            file.write("  <td class='NO_RESULT'>No result</td>\n")
    file.write("</tr>\n")

file.write("""
                    </tbody>
                </table>
            </div>
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
