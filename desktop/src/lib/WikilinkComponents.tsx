/**
 * Custom Streamdown component overrides for wikilink navigation.
 *
 * Intercepts links with the `#brain/` fragment prefix (created by remarkWikilinks)
 * and calls onNavigateToNote instead of navigating to a URL.
 */
import type { Components } from "streamdown";

const BRAIN_PREFIX = "#brain/";

export function createWikilinkComponents(
  onNavigateToNote?: (title: string) => void,
): Partial<Components> {
  return {
    a: ({ href, children, ...props }) => {
      if (href?.startsWith(BRAIN_PREFIX) && onNavigateToNote) {
        const title = href.slice(BRAIN_PREFIX.length);
        return (
          <a
            {...props}
            href="#"
            onClick={(e) => {
              e.preventDefault();
              onNavigateToNote(title);
            }}
            className="text-blue-400 underline decoration-dotted cursor-pointer hover:text-blue-300"
          >
            {children}
          </a>
        );
      }
      // Regular links: open externally
      return (
        <a {...props} href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    },
  };
}
