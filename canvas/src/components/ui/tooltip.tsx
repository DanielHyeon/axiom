import * as React from "react"
import { cn } from "@/lib/utils"

// 툴팁 컴포넌트 — shadcn/ui Tooltip 호환 stub (CSS title 기반 경량 구현)

const TooltipProvider: React.FC<{ children: React.ReactNode; delayDuration?: number }> = ({
  children,
}) => <>{children}</>

const Tooltip: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <>{children}</>
)

const TooltipTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }
>(({ className, ...props }, ref) => (
  <button ref={ref} className={cn(className)} {...props} />
))
TooltipTrigger.displayName = "TooltipTrigger"

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & { side?: string; sideOffset?: number }
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-md",
      className,
    )}
    {...props}
  />
))
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
