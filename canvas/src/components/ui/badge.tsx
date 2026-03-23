import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
 variant?: "default" | "secondary" | "destructive" | "outline" | "ai"
}

const badgeVariants = {
 variant: {
 default: "bg-primary text-primary-foreground hover:bg-primary/90",
 secondary: "bg-muted text-muted-foreground hover:bg-border",
 destructive: "bg-destructive text-primary-foreground hover:bg-destructive",
 outline: "text-muted-foreground border border-border",
 ai: "bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-primary-foreground border-0",
 }
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
 return (
 <div
 className={cn(
 "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
 badgeVariants.variant[variant],
 className
 )}
 {...props}
 />
 )
}

export { Badge, badgeVariants }
