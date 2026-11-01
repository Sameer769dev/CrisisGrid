import os
import time
from playwright.sync_api import sync_playwright

def smooth_scroll(page, target_y, steps=25, duration=0.8):
    try:
        current_y = page.evaluate("window.scrollY || window.pageYOffset || 0")
        diff = target_y - current_y
        for i in range(1, steps + 1):
            t = i / steps
            # Smooth cubic ease-in-out
            ease = t * t * (3 - 2 * t)
            page.evaluate(f"window.scrollTo(0, {current_y + diff * ease})")
            time.sleep(duration / steps)
    except Exception as e:
        print(f"Scroll notice: {e}", flush=True)

def safe_bounding_box(locator):
    try:
        if locator.count() > 0 and locator.first.is_visible():
            return locator.first.bounding_box()
    except Exception:
        pass
    return None

def safe_click(locator, timeout=2500, force=True):
    try:
        if locator.count() > 0 and locator.first.is_visible():
            locator.first.click(timeout=timeout, force=force)
            return True
    except Exception as e:
        print(f"safe_click notice: {e}", flush=True)
    return False

def record_screen():
    print("=" * 70, flush=True)
    print("CRISISGRID — 3-MINUTE RAW SCREEN RECORDER (CLEAN 1080P WALKTHROUGH)", flush=True)
    print("=" * 70, flush=True)

    os.makedirs("demo_3min/raw_video", exist_ok=True)
    for f in os.listdir("demo_3min/raw_video"):
        if f.endswith(".webm"):
            try:
                os.remove(os.path.join("demo_3min/raw_video", f))
            except Exception:
                pass

    start_wall = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--hide-scrollbars",
                "--font-render-hinting=none"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            record_video_dir="demo_3min/raw_video",
            record_video_size={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        print("Navigating to http://localhost:3000 ...", flush=True)
        page.goto("http://localhost:3000", wait_until="networkidle")
        time.sleep(1.5)

        # =====================================================================
        # ACT 1 (0:00 - 0:33, ~33s): Intro Hook & Disaster Gallery Selection
        # =====================================================================
        print("Act 1: Intro Hook & Mission Control Ingestion...", flush=True)
        # Hold on top status bar & Mission Control header (0:00 - 0:08)
        time.sleep(6.5)

        # Smooth scroll down to 9-scene disaster gallery (0:08 - 0:13)
        sample_strip = page.locator(".sample-strip")
        box = safe_bounding_box(sample_strip)
        if box:
            smooth_scroll(page, max(0, box["y"] - 60), steps=25, duration=0.8)
        else:
            smooth_scroll(page, 480, steps=25, duration=0.8)
        time.sleep(1.0)

        # Click category filter buttons: EARTHQUAKE -> LANDSLIDE -> FLOOD (0:13 - 0:21)
        for cat in ["EARTHQUAKE", "LANDSLIDE", "FLOOD"]:
            btn = page.locator(f"button.trace-filter:has-text('{cat}')")
            safe_click(btn)
            time.sleep(1.8)

        # Click LOAD SCENE on Urban Flood (0:21 - 0:25)
        load_btn = page.locator(".sample-card").first.locator("button.btn-pipeline")
        safe_click(load_btn)
        time.sleep(1.8)

        # Scroll back up to Mission Control to see loaded image & radio WAV (0:25 - 0:33)
        smooth_scroll(page, 0, steps=25, duration=0.8)
        time.sleep(5.5)

        # =====================================================================
        # ACT 2 (0:33 - 1:00, ~27s): 9x SAM-3.1 Parallel Scan & Voice Transcribe
        # =====================================================================
        print("Act 2: Executing Full Pipeline (9x SAM-3.1 + Muse Voice)...", flush=True)
        pipeline_btn = page.locator("button.btn-pipeline:has-text('RUN FULL PIPELINE')")
        if safe_click(pipeline_btn):
            print("  -> Clicked RUN FULL PIPELINE", flush=True)

        # Watch live telemetry timer tick for 8 seconds
        time.sleep(8.0)

        # Scroll slightly to show progress chips & live trace beginning
        smooth_scroll(page, 200, steps=20, duration=0.6)
        time.sleep(4.0)

        # Scroll to tactical canvas & trace grid to see newly populated 8 detections & masks (0:45 - 1:00)
        grid_loc = page.locator(".grid")
        box = safe_bounding_box(grid_loc)
        if box:
            smooth_scroll(page, max(0, box["y"] - 30), steps=25, duration=0.8)
        else:
            smooth_scroll(page, 720, steps=25, duration=0.8)
        time.sleep(14.0)

        # =====================================================================
        # ACT 3 (1:00 - 1:32, ~32s): Triage & Geometric Rejection / Re-Route
        # =====================================================================
        print("Act 3: Inspecting Triage & Geometric Re-Route Proof...", flush=True)
        # Scroll the live trace box to show the exact rejection & verification entries
        trace_el = page.locator(".trace-live")
        if trace_el.count() > 0 and trace_el.first.is_visible():
            for sy in [60, 160, 300, 120]:
                try:
                    trace_el.first.evaluate(f"el => el.scrollTo({{ top: {sy}, behavior: 'smooth' }})")
                except Exception:
                    pass
                time.sleep(2.0)

        # Click the corridor on the Tactical Canvas to trigger inspection details
        canvas = page.locator("canvas.tactical-canvas")
        if canvas.count() > 0 and canvas.first.is_visible():
            box = canvas.first.bounding_box()
            if box:
                # Click near middle road corridor
                page.mouse.click(box["x"] + box["width"] * 0.48, box["y"] + box["height"] * 0.65)
                time.sleep(2.5)
                # Click the landing zone circle
                page.mouse.click(box["x"] + box["width"] * 0.35, box["y"] + box["height"] * 0.85)
                time.sleep(2.5)

        # Scroll to triage panel if visible
        triage_loc = page.locator(".triage-panel")
        box = safe_bounding_box(triage_loc)
        if box:
            smooth_scroll(page, max(0, box["y"] - 40), steps=25, duration=0.8)
        time.sleep(10.0)

        # =====================================================================
        # ACT 4 (1:32 - 2:08, ~36s): Muse Wonder 1.0 Dispatch & Briefing Card
        # =====================================================================
        print("Act 4: High-Effort Wonder Dispatch & Tactical Briefing Card...", flush=True)
        dispatch_loc = page.locator(".dispatch-panel")
        box = safe_bounding_box(dispatch_loc)
        if box:
            smooth_scroll(page, max(0, box["y"] - 30), steps=25, duration=0.8)
        else:
            smooth_scroll(page, 1500, steps=25, duration=0.8)
        time.sleep(4.0)

        # Hover over dispatch units in the table
        unit_rows = page.locator(".unit-table tbody tr")
        if unit_rows.count() > 0:
            for i in range(min(4, unit_rows.count())):
                try:
                    unit_rows.nth(i).hover()
                except Exception:
                    pass
                time.sleep(1.8)

        # Hover over briefing card image
        card_img = page.locator("img.briefing-card, .briefing-card img, .card-image")
        if card_img.count() > 0 and card_img.first.is_visible():
            try:
                card_img.first.hover()
            except Exception:
                pass
            time.sleep(3.0)

        # Hover & click Export buttons
        iap_btn = page.locator("button:has-text('EXPORT IAP (.MD)')")
        if iap_btn.count() > 0 and iap_btn.first.is_visible():
            try:
                iap_btn.first.hover()
                time.sleep(1.2)
                safe_click(iap_btn, force=True)
                time.sleep(1.2)
            except Exception:
                pass

        json_btn = page.locator("button:has-text('EXPORT JSON (.JSON)')")
        if json_btn.count() > 0 and json_btn.first.is_visible():
            try:
                json_btn.first.hover()
                time.sleep(1.5)
            except Exception:
                pass

        time.sleep(14.0)

        # =====================================================================
        # ACT 5 (2:08 - 2:42, ~34s): USGS Live Quakes & Clearance Verification
        # =====================================================================
        print("Act 5: Live USGS Quakes & Before/After Clearance Delta...", flush=True)
        # Scroll to USGS section in PresetPanel
        usgs_btn = page.locator("button:has-text('FETCH LIVE M4.5+ (PAST 24H)')")
        box = safe_bounding_box(usgs_btn)
        if box:
            smooth_scroll(page, max(0, box["y"] - 180), steps=25, duration=0.8)
        else:
            smooth_scroll(page, 2200, steps=25, duration=0.8)
        time.sleep(2.0)

        # Wait up to 10s if button is currently busy/disabled, then click
        t_wait = 0.0
        while t_wait < 10.0:
            try:
                if usgs_btn.count() > 0 and usgs_btn.first.is_enabled():
                    break
            except Exception:
                pass
            time.sleep(0.5)
            t_wait += 0.5

        safe_click(usgs_btn, timeout=2000, force=True)
        time.sleep(4.0)

        # Scroll to Before/After Delta Panel
        delta_panel = page.locator("section[aria-label='Before after damage delta']")
        box = safe_bounding_box(delta_panel)
        if box:
            smooth_scroll(page, max(0, box["y"] - 40), steps=25, duration=0.8)
        time.sleep(1.5)

        # Load clearance pair & run verification
        load_pair_btn = page.locator("button:has-text('LOAD BEFORE + AFTER PAIR')")
        safe_click(load_pair_btn, timeout=2000, force=True)
        time.sleep(3.0)

        run_clear_btn = page.locator("button:has-text('1-CLICK RUN BEFORE')")
        if run_clear_btn.count() > 0 and run_clear_btn.first.is_visible():
            try:
                run_clear_btn.first.hover()
            except Exception:
                pass
            time.sleep(2.0)

        # Scroll smoothly back to top for clean outro hold
        smooth_scroll(page, 0, steps=30, duration=1.0)

        # Check total elapsed time so we hit exactly 162.5 seconds
        elapsed = time.time() - start_wall
        target_total = 162.5
        remaining = target_total - elapsed
        if remaining > 0:
            print(f"Holding outro for remaining {remaining:.2f}s to match master audio (162.0s)...", flush=True)
            time.sleep(remaining)

        print("Recording complete. Closing browser...", flush=True)
        page.close()
        context.close()
        browser.close()
        print("Playwright video captured successfully!", flush=True)

if __name__ == "__main__":
    record_screen()
