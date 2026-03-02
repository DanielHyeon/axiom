import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
 variant?: "default" | "secondary" | "destructive" | "outline" | "ai"
}

const badgeVariants = {
 variant: {
 default: "bg-primary text-white hover:bg-primary/90",
 secondary: "bg-[#F5F5F5] text-[#5E5E5E] hover:bg-[#E5E5E5]",
 destructive: "bg-destructive text-white hover:bg-destructive",
 outline: "text-[#5E5E5E] border border-[#E5E5E5]",
 ai: "bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-white border-0",
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
