import { clsx, type ClassValue } from "clsx"

// We are using TailwindCSS v4 with Vite so standard twMerge won't have the V4 context by default.
// In simple components, basic twMerge is fine, but extending it for specific custom utilities can be done here.
// For now, standard twMerge is safe enough for basic padding/margin/color overrides.
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}
