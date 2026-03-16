import type { DetailedHTMLProps, HTMLAttributes, MouseEventHandler, SyntheticEvent } from 'react';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      's-app-nav': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
      's-contextual-save-bar': DetailedHTMLProps<HTMLAttributes<HTMLElement> & {
        message?: string;
        onSave?: () => void;
        onDiscard?: () => void;
        saveLoading?: boolean | string;
      }, HTMLElement>;
      's-page': DetailedHTMLProps<HTMLAttributes<HTMLElement> & {
        title?: string;
        'primary-action'?: string;
        'back-action'?: string;
      }, HTMLElement>;
      's-section': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
      's-stack': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { direction?: 'block' | 'inline'; gap?: string; 'align-items'?: string; 'justify-content'?: string; wrap?: string }, HTMLElement>;
      's-grid': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { columns?: string; gap?: string }, HTMLElement>;
      's-box': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { padding?: string; background?: string; 'border-radius'?: string; border?: string }, HTMLElement>;
      's-button': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { variant?: 'primary' | 'secondary' | 'plain' | 'destructive'; size?: 'slim' | 'medium' | 'large'; disabled?: boolean | string; loading?: boolean | string; onClick?: MouseEventHandler<HTMLElement> }, HTMLElement>;
      's-heading': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' }, HTMLElement>;
      's-paragraph': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { tone?: 'subdued' | 'success' | 'caution' | 'critical' }, HTMLElement>;
      's-text': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { variant?: string; tone?: string; 'font-weight'?: string; fontWeight?: string }, HTMLElement>;
      's-badge': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { tone?: 'success' | 'warning' | 'critical' | 'info' | 'attention' | 'new'; size?: 'small' | 'medium' }, HTMLElement>;
      's-banner': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { tone?: 'success' | 'warning' | 'critical' | 'info'; title?: string; onDismiss?: (e: SyntheticEvent) => void }, HTMLElement>;
      's-divider': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
      's-spinner': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { size?: 'small' | 'large' }, HTMLElement>;
      's-icon': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { source?: string }, HTMLElement>;
      's-text-field': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { label?: string; value?: string; placeholder?: string; type?: string; disabled?: boolean | string; onChange?: (e: SyntheticEvent) => void }, HTMLElement>;
      's-select': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { label?: string; value?: string; onChange?: (e: SyntheticEvent) => void }, HTMLElement>;
      's-modal': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { open?: boolean | string; title?: string }, HTMLElement>;
      's-list': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
      's-link': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { href?: string; tone?: string }, HTMLElement>;
      's-table': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
      's-clickable-chip': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { selected?: boolean | string; onClick?: MouseEventHandler<HTMLElement> }, HTMLElement>;
      's-tooltip': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { content?: string }, HTMLElement>;
      's-popover': DetailedHTMLProps<HTMLAttributes<HTMLElement> & { active?: boolean | string }, HTMLElement>;
      's-menu': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
      's-chip': DetailedHTMLProps<HTMLAttributes<HTMLElement>, HTMLElement>;
    }
  }
}
