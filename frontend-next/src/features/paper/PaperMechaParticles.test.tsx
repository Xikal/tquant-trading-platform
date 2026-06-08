import { render } from "solid-js/web";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PaperMechaParticles } from "./PaperMechaParticles";

describe("paper mecha particle lifecycle", () => {
  let requestAnimationFrameMock: ReturnType<typeof vi.fn>;
  let cancelAnimationFrameMock: ReturnType<typeof vi.fn>;
  let addListenerSpy: ReturnType<typeof vi.spyOn>;
  let removeListenerSpy: ReturnType<typeof vi.spyOn>;
  let matchMediaMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeCanvasContext());
    vi.spyOn(HTMLCanvasElement.prototype, "getBoundingClientRect").mockReturnValue({ width: 320, height: 180, x: 0, y: 0, top: 0, right: 320, bottom: 180, left: 0, toJSON: () => ({}) });
    vi.stubGlobal("devicePixelRatio", 1);
    matchMediaMock = vi.fn(() => mediaQuery(false));
    requestAnimationFrameMock = vi.fn(() => 11);
    cancelAnimationFrameMock = vi.fn();
    vi.stubGlobal("matchMedia", matchMediaMock);
    vi.stubGlobal("requestAnimationFrame", requestAnimationFrameMock);
    vi.stubGlobal("cancelAnimationFrame", cancelAnimationFrameMock);
    addListenerSpy = vi.spyOn(window, "addEventListener");
    removeListenerSpy = vi.spyOn(window, "removeEventListener");
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("cancels animation and resize listeners on cleanup", () => {
    const dispose = render(() => <PaperMechaParticles state="buy" />, document.body);

    expect(requestAnimationFrameMock).toHaveBeenCalled();
    expect(addListenerSpy).toHaveBeenCalledWith("resize", expect.any(Function));

    dispose();
    expect(cancelAnimationFrameMock).toHaveBeenCalledWith(11);
    expect(removeListenerSpy).toHaveBeenCalledWith("resize", expect.any(Function));
  });

  it("does not start animation when reduced motion is requested", () => {
    matchMediaMock.mockReturnValue(createControllableMediaQuery(true).query);

    const dispose = render(() => <PaperMechaParticles state="profit" />, document.body);

    expect(requestAnimationFrameMock).not.toHaveBeenCalled();
    dispose();
  });

  it("stops animation listeners when reduced motion is enabled at runtime", () => {
    const media = createControllableMediaQuery(false);
    matchMediaMock.mockReturnValue(media.query);

    const dispose = render(() => <PaperMechaParticles state="sell" />, document.body);

    expect(requestAnimationFrameMock).toHaveBeenCalled();
    expect(addListenerSpy).toHaveBeenCalledWith("resize", expect.any(Function));

    media.setMatches(true);

    expect(cancelAnimationFrameMock).toHaveBeenCalledWith(11);
    expect(removeListenerSpy).toHaveBeenCalledWith("resize", expect.any(Function));

    dispose();
    expect(media.query.removeEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });
});

function mediaQuery(matches: boolean): MediaQueryList {
  return {
    matches,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  } as MediaQueryList;
}

function createControllableMediaQuery(initialMatches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>();
  const query = mediaQuery(initialMatches);
  query.addEventListener = vi.fn((eventName: string, listener: EventListenerOrEventListenerObject) => {
    if (eventName !== "change" || typeof listener !== "function") return;
    listeners.add(listener as (event: MediaQueryListEvent) => void);
  }) as MediaQueryList["addEventListener"];
  query.removeEventListener = vi.fn((eventName: string, listener: EventListenerOrEventListenerObject) => {
    if (eventName !== "change" || typeof listener !== "function") return;
    listeners.delete(listener as (event: MediaQueryListEvent) => void);
  }) as MediaQueryList["removeEventListener"];

  return {
    query,
    setMatches(matches: boolean) {
      Object.defineProperty(query, "matches", { configurable: true, value: matches });
      listeners.forEach((listener) => listener({ matches, media: query.media } as MediaQueryListEvent));
    },
  };
}

function fakeCanvasContext(): CanvasRenderingContext2D {
  return {
    arc: vi.fn(),
    beginPath: vi.fn(),
    clearRect: vi.fn(),
    closePath: vi.fn(),
    fill: vi.fn(),
    lineTo: vi.fn(),
    moveTo: vi.fn(),
    restore: vi.fn(),
    save: vi.fn(),
    setTransform: vi.fn(),
    stroke: vi.fn(),
    set fillStyle(_value: string) {},
    set globalAlpha(_value: number) {},
    set globalCompositeOperation(_value: string) {},
    set lineWidth(_value: number) {},
    set strokeStyle(_value: string) {},
  } as unknown as CanvasRenderingContext2D;
}
