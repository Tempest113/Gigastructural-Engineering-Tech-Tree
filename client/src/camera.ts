// Stage 3 slice 2: the camera -- one scale+translate transform applied to the world container.
// Per-node world coordinates (the P-2/D-13 layout geometry already in client/src/main.ts) are
// never touched; only this transform changes what's visible.

import type { Application, Container } from "pixi.js";

export interface ContentBBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface Camera {
  /** World point currently under a given screen point. */
  screenToWorld(sx: number, sy: number): { x: number; y: number };
  /** Screen point a given world point currently projects to. */
  worldToScreen(wx: number, wy: number): { x: number; y: number };
  getScale(): number;
  getMinScale(): number;
  getMaxScale(): number;
  /** Sets scale, anchored so the world point currently under (anchorSx, anchorSy) stays there.
   * Clamped to [minScale, maxScale] and re-clamps pan afterward. */
  setScale(newScale: number, anchorSx: number, anchorSy: number): void;
  /** Screen-space pan by (dx, dy) pixels, clamped so content can't be dragged fully off-screen. */
  panBy(dx: number, dy: number): void;
  /** The exact slice-1 fit-to-viewport view: recomputes the fit scale from the current viewport
   * size and frames the content identically to how main.ts originally framed it on load. */
  resetToFit(): void;
  /** Recomputes the fit scale / min-zoom clamp from the current viewport size (window resize) and
   * re-clamps the current view without otherwise moving it, unless the current scale is now below
   * the new minimum. */
  handleResize(): void;
  onChange(cb: () => void): void;
  /** Removes all DOM/window listeners this camera installed. */
  destroy(): void;
}

const MAX_SCALE = 1.5; // 1.5x native (100%) world scale, per this slice's spec
const FIT_MARGIN_FACTOR = 0.98; // matches slice 1's original fit-to-viewport framing exactly
const PAN_MARGIN_FRACTION = 0.35; // "a modest margin", as a fraction of each viewport dimension
const WHEEL_ZOOM_SENSITIVITY = 1.0015;
const KEYBOARD_PAN_STEP = 60; // screen px per arrow-key press
const KEYBOARD_ZOOM_FACTOR = 1.2;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function distance(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function createCamera(app: Application, world: Container, contentBBox: ContentBBox): Camera {
  let minScale = computeFitScale();
  const changeListeners: (() => void)[] = [];

  function computeFitScale(): number {
    return (
      Math.min(app.screen.width / contentBBox.width, app.screen.height / contentBBox.height) * FIT_MARGIN_FACTOR
    );
  }

  function notify(): void {
    for (const cb of changeListeners) cb();
  }

  function screenToWorld(sx: number, sy: number): { x: number; y: number } {
    return { x: (sx - world.position.x) / world.scale.x, y: (sy - world.position.y) / world.scale.y };
  }

  function worldToScreen(wx: number, wy: number): { x: number; y: number } {
    return { x: wx * world.scale.x + world.position.x, y: wy * world.scale.y + world.position.y };
  }

  function clampPan(): void {
    const scale = world.scale.x;
    const marginX = app.screen.width * PAN_MARGIN_FRACTION;
    const marginY = app.screen.height * PAN_MARGIN_FRACTION;
    const contentScreenLeft = contentBBox.left * scale;
    const contentScreenRight = (contentBBox.left + contentBBox.width) * scale;
    const contentScreenTop = contentBBox.top * scale;
    const contentScreenBottom = (contentBBox.top + contentBBox.height) * scale;

    const minPX = -marginX - contentScreenRight;
    const maxPX = app.screen.width + marginX - contentScreenLeft;
    const minPY = -marginY - contentScreenBottom;
    const maxPY = app.screen.height + marginY - contentScreenTop;

    world.position.x = minPX <= maxPX ? clamp(world.position.x, minPX, maxPX) : (minPX + maxPX) / 2;
    world.position.y = minPY <= maxPY ? clamp(world.position.y, minPY, maxPY) : (minPY + maxPY) / 2;
  }

  function setScale(newScaleRaw: number, anchorSx: number, anchorSy: number): void {
    const worldPt = screenToWorld(anchorSx, anchorSy);
    const newScale = clamp(newScaleRaw, minScale, MAX_SCALE);
    world.scale.set(newScale);
    world.position.set(anchorSx - worldPt.x * newScale, anchorSy - worldPt.y * newScale);
    clampPan();
    notify();
  }

  function panBy(dx: number, dy: number): void {
    world.position.x += dx;
    world.position.y += dy;
    clampPan();
    notify();
  }

  function resetToFit(): void {
    minScale = computeFitScale();
    world.scale.set(minScale);
    // Exact slice-1 framing formula -- point 2's "initial state must not change" requirement.
    world.position.set(-contentBBox.left * minScale + 8, -contentBBox.top * minScale + 8);
    notify();
  }

  function handleResize(): void {
    minScale = computeFitScale();
    if (world.scale.x < minScale) {
      setScale(minScale, app.screen.width / 2, app.screen.height / 2);
    } else {
      clampPan();
      notify();
    }
  }

  // --- Wheel (mouse wheel + trackpad scroll/pinch, both delivered as wheel events) ---
  const onWheel = (e: WheelEvent): void => {
    e.preventDefault();
    const rect = app.canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    const factor = Math.pow(WHEEL_ZOOM_SENSITIVITY, -e.deltaY);
    setScale(world.scale.x * factor, sx, sy);
  };
  app.canvas.addEventListener("wheel", onWheel, { passive: false });

  // --- Pointer events: single-pointer drag pans, two-pointer pinch zooms. Pointer Events unify
  // mouse/touch/pen (CLAUDE.md's "Pointer Events only" rule), so this is also the touch path. ---
  const activePointers = new Map<number, { x: number; y: number }>();
  let dragLast: { x: number; y: number } | null = null;
  let pinchStartDist: number | null = null;

  const onPointerDown = (e: PointerEvent): void => {
    app.canvas.setPointerCapture(e.pointerId);
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (activePointers.size === 1) {
      dragLast = { x: e.clientX, y: e.clientY };
    } else if (activePointers.size === 2) {
      dragLast = null;
      const pts = [...activePointers.values()];
      pinchStartDist = distance(pts[0]!, pts[1]!);
    }
  };

  const onPointerMove = (e: PointerEvent): void => {
    if (!activePointers.has(e.pointerId)) return;
    activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const rect = app.canvas.getBoundingClientRect();

    if (activePointers.size === 2) {
      const pts = [...activePointers.values()];
      const dist = distance(pts[0]!, pts[1]!);
      const midSx = (pts[0]!.x + pts[1]!.x) / 2 - rect.left;
      const midSy = (pts[0]!.y + pts[1]!.y) / 2 - rect.top;
      if (pinchStartDist !== null && pinchStartDist > 0) {
        setScale(world.scale.x * (dist / pinchStartDist), midSx, midSy);
      }
      pinchStartDist = dist;
    } else if (activePointers.size === 1 && dragLast) {
      const dx = e.clientX - dragLast.x;
      const dy = e.clientY - dragLast.y;
      dragLast = { x: e.clientX, y: e.clientY };
      panBy(dx, dy);
    }
  };

  const onPointerEnd = (e: PointerEvent): void => {
    activePointers.delete(e.pointerId);
    if (activePointers.size < 2) pinchStartDist = null;
    if (activePointers.size === 1) {
      dragLast = [...activePointers.values()][0]!;
    } else {
      dragLast = null;
    }
  };

  app.canvas.addEventListener("pointerdown", onPointerDown);
  app.canvas.addEventListener("pointermove", onPointerMove);
  app.canvas.addEventListener("pointerup", onPointerEnd);
  app.canvas.addEventListener("pointercancel", onPointerEnd);

  // --- Keyboard: arrows pan, +/- zoom about viewport centre, 0 resets to fit, 1 sets 100%. ---
  // Listens on `window`, so it fires for every keydown that bubbles up regardless of focus --
  // including a text input (the search field). Without this guard, typing "_" (or any other
  // shortcut character, e.g. "0"/"1") into the search box zoomed the camera instead of entering
  // the character: a real reported bug, "-"/"_" are the camera's own zoom-out shortcut. Every
  // printable character must reach a focused text-entry element untouched.
  const onKeyDown = (e: KeyboardEvent): void => {
    const target = e.target as HTMLElement | null;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
      return;
    }
    const cx = app.screen.width / 2;
    const cy = app.screen.height / 2;
    switch (e.key) {
      case "ArrowUp":
        panBy(0, KEYBOARD_PAN_STEP);
        break;
      case "ArrowDown":
        panBy(0, -KEYBOARD_PAN_STEP);
        break;
      case "ArrowLeft":
        panBy(KEYBOARD_PAN_STEP, 0);
        break;
      case "ArrowRight":
        panBy(-KEYBOARD_PAN_STEP, 0);
        break;
      case "+":
      case "=":
        setScale(world.scale.x * KEYBOARD_ZOOM_FACTOR, cx, cy);
        break;
      case "-":
      case "_":
        setScale(world.scale.x / KEYBOARD_ZOOM_FACTOR, cx, cy);
        break;
      case "0":
        resetToFit();
        break;
      case "1":
        setScale(1.0, cx, cy);
        break;
      default:
        return;
    }
    e.preventDefault();
  };
  window.addEventListener("keydown", onKeyDown);

  // --- Resize: recompute fit scale / min-zoom clamp. Wrapped in rAF so Pixi's own `resizeTo`
  // handler (which resizes app.screen) has already run before we read it. ---
  const onResize = (): void => {
    requestAnimationFrame(handleResize);
  };
  window.addEventListener("resize", onResize);

  return {
    screenToWorld,
    worldToScreen,
    getScale: () => world.scale.x,
    getMinScale: () => minScale,
    getMaxScale: () => MAX_SCALE,
    setScale,
    panBy,
    resetToFit,
    handleResize,
    onChange: (cb) => changeListeners.push(cb),
    destroy: () => {
      app.canvas.removeEventListener("wheel", onWheel);
      app.canvas.removeEventListener("pointerdown", onPointerDown);
      app.canvas.removeEventListener("pointermove", onPointerMove);
      app.canvas.removeEventListener("pointerup", onPointerEnd);
      app.canvas.removeEventListener("pointercancel", onPointerEnd);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", onResize);
    },
  };
}
