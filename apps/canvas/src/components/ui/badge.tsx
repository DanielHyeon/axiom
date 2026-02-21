import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: "default" | "secondary" | "destructive" | "outline" | "ai"
}

const badgeVariants = {
    variant: {
        default: "bg-blue-600 text-white hover:bg-blue-700",
        secondary: "bg-neutral-800 text-neutral-100 hover:bg-neutral-700",
        destructive: "bg-red-500 text-white hover:bg-red-600",
        outline: "text-neutral-300 border border-neutral-700",
        ai: "bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-white border-0",
    }
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
    return (
        <div
            className={cn(
                "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2",
                badgeVariants.variant[variant],
                className
            )}
            {...props}
        />
    )
}

export { Badge, badgeVariants }
