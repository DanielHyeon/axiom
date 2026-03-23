import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Dialog 컴포넌트 — shadcn/ui 호환 + 접근성 완비.
 * Phase 2 C3 수정: focus trap + Escape 키 + role="dialog" + aria-modal.
 *
 * @radix-ui/react-dialog 없이 네이티브 구현:
 * - 열릴 때 첫 번째 포커스 가능 요소로 자동 포커스
 * - Tab 키 순환 (focus trap)
 * - Escape 키로 닫기
 * - 닫힐 때 트리거 요소로 포커스 복원
 * - 오버레이 클릭으로 닫기
 */

interface DialogProps {
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: React.ReactNode
}

function Dialog({ open, onOpenChange, children }: DialogProps) {
  const contentRef = React.useRef<HTMLDivElement>(null)
  const triggerRef = React.useRef<HTMLElement | null>(null)

  // 열릴 때 현재 포커스 요소 저장 + 다이얼로그 내부로 포커스 이동
  React.useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement as HTMLElement
      // 다음 프레임에서 포커스 이동 (렌더링 완료 후)
      requestAnimationFrame(() => {
        const focusable = contentRef.current?.querySelector<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        focusable?.focus()
      })
    } else if (triggerRef.current) {
      // 닫힐 때 트리거로 포커스 복원
      triggerRef.current.focus()
      triggerRef.current = null
    }
  }, [open])

  // Escape 키 + focus trap
  React.useEffect(() => {
    if (!open) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onOpenChange?.(false)
        return
      }

      // Tab focus trap: 다이얼로그 내부에서만 순환
      if (e.key === 'Tab' && contentRef.current) {
        const focusables = contentRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusables.length === 0) return

        const first = focusables[0]
        const last = focusables[focusables.length - 1]

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    // body 스크롤 방지
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = prev
    }
  }, [open, onOpenChange])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 배경 오버레이 — 클릭으로 닫기 */}
      <div
        className="fixed inset-0 bg-black/80"
        onClick={() => onOpenChange?.(false)}
        aria-hidden="true"
      />
      {/* 다이얼로그 컨테이너 — 접근성 속성 완비 */}
      <div
        ref={contentRef}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  )
}

const DialogContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "relative z-50 grid w-full max-w-lg gap-4 border bg-background p-6 shadow-lg sm:rounded-lg",
      className,
    )}
    onClick={(e) => e.stopPropagation()}
    {...props}
  >
    {children}
  </div>
))
DialogContent.displayName = "DialogContent"

function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}
      {...props}
    />
  )
}

function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
      {...props}
    />
  )
}

const DialogTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h2
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
DialogTitle.displayName = "DialogTitle"

const DialogDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
DialogDescription.displayName = "DialogDescription"

// DialogTrigger — open/close 토글 (선택적 사용)
function DialogTrigger({
  children,
  asChild: _asChild,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) {
  return <button type="button" {...props}>{children}</button>
}

// DialogClose — 다이얼로그 내부 닫기 버튼 (선택적 사용)
function DialogClose({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" {...props}>{children}</button>
}

export {
  Dialog,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
