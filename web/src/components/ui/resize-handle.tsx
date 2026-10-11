/* A focusable separator is the WAI-ARIA "window splitter", a keyboard-operable widget that the
   jsx-a11y rules cannot tell from a plain separator. */
/* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex */
import { useState } from "react";
import { cn } from "#/utils/utils";

interface ResizeHandleProps {
  onMouseDown: (e: React.MouseEvent) => void;
  /** Keyboard resizing: +1 / -1 for the Right / Left arrow keys. */
  onKeyResize?: (direction: 1 | -1) => void;
  className?: string;
  /** While the parent panel drag is active, keep the grip line highlighted. */
  isDragging?: boolean;
  testId?: string;
  /** Accessible name and current size (px) of the thing being resized. */
  label: string;
  valueNow: number;
}

/** A draggable divider that can also be focused and moved with the arrow keys. */
export function ResizeHandle({
  onMouseDown,
  onKeyResize,
  className,
  isDragging = false,
  testId,
  label,
  valueNow,
}: ResizeHandleProps) {
  const [isHovering, setIsHovering] = useState(false);
  const lineActive = isDragging || isHovering;

  return (
    <div
      data-testid={testId}
      className={cn("relative z-10 w-0 shrink-0 self-stretch", className)}
    >
      {/* A focusable separator is the WAI-ARIA "window splitter": a keyboard-operable widget. */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={label}
        aria-valuenow={valueNow}
        tabIndex={0}
        className="absolute inset-y-0 left-1/2 w-3 min-w-3 -translate-x-1/2 cursor-ew-resize focus-visible:outline-2 focus-visible:outline-primary"
        onMouseDown={onMouseDown}
        onMouseEnter={() => setIsHovering(true)}
        onMouseLeave={() => setIsHovering(false)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") onKeyResize?.(1);
          else if (e.key === "ArrowLeft") onKeyResize?.(-1);
          else return;
          e.preventDefault();
        }}
      />
      <div
        className={cn(
          "pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 transition-colors",
          lineActive ? "bg-contrast" : "bg-transparent",
        )}
        aria-hidden
      />
    </div>
  );
}
