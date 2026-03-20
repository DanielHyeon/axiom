import { useTranslation } from 'react-i18next';
import { useThemeStore, type ThemeMode } from '@/stores/themeStore';

export function ThemeToggle() {
 const { t } = useTranslation();
 const { mode, setMode } = useThemeStore();
 const cycle = () => {
 const next: ThemeMode = mode === 'light' ? 'dark' : mode === 'dark' ? 'system' : 'light';
 setMode(next);
 };
 const label = t(`theme.${mode}`);
 return (
 <button
 type="button"
 onClick={cycle}
 className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
 aria-label={label}
 title={label}
 >
 {label}
 </button>
 );
}
