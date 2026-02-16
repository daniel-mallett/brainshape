/**
 * Hook that attaches a delegated click handler to a container ref,
 * intercepting clicks on wikilink anchors (href="#brain/...").
 *
 * Uses event delegation so the callback is always current — avoids
 * stale closures from Streamdown's internal block memoization.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const BRAIN_PREFIX = "#brain/";

export function useWikilinkClick(
  onNavigateToNote?: (title: string) => void,
): (node: HTMLElement | null) => void {
  const callbackRef = useRef(onNavigateToNote);
  callbackRef.current = onNavigateToNote;

  const [container, setContainer] = useState<HTMLElement | null>(null);

  // Callback ref to capture the DOM element
  const ref = useCallback((node: HTMLElement | null) => {
    setContainer(node);
  }, []);

  useEffect(() => {
    if (!container) return;

    function handleClick(e: MouseEvent) {
      const anchor = (e.target as HTMLElement).closest?.("a");
      if (!anchor) return;

      const href = anchor.getAttribute("href");
      if (href?.startsWith(BRAIN_PREFIX) && callbackRef.current) {
        e.preventDefault();
        const title = decodeURIComponent(href.slice(BRAIN_PREFIX.length));
        callbackRef.current(title);
      }
    }

    container.addEventListener("click", handleClick);
    return () => container.removeEventListener("click", handleClick);
  }, [container]);

  return ref;
}
