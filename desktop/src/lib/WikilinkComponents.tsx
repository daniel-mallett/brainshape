/**
 * Custom Streamdown component overrides for wikilink navigation.
 *
 * Renders wikilinks (href="#brain/...") as styled inline links.
 * Actual click handling is done via event delegation in the parent
 * component (useWikilinkClick hook) to avoid stale closure issues
 * with Streamdown's internal block memoization.
 */
import type { Components } from "streamdown";

const BRAIN_PREFIX = "#brain/";

export const wikilinkComponents: Partial<Components> = {
  a: ({ href, children }) => {
    if (href?.startsWith(BRAIN_PREFIX)) {
      return (
        <a
          href={href}
          className="underline decoration-dotted cursor-pointer"
          style={{ color: "var(--editor-link)" }}
        >
          {children}
        </a>
      );
    }
    // Regular links: open externally
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
};
