/* Shopify Polaris Web Components (s-*) - JSX IntrinsicElements */

import 'react';

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
    's-page': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        title?: string;
        'back-action'?: string;
      },
      HTMLElement
    >;
    's-card': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & { title?: string },
      HTMLElement
    >;
    's-banner': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        tone?: 'critical' | 'warning' | 'success' | 'info';
        title?: string;
      },
      HTMLElement
    >;
    's-layout': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & { variant?: string },
      HTMLElement
    >;
    's-text': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        variant?: string;
        tone?: string;
      },
      HTMLElement
    >;
    's-badge': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & { tone?: string },
      HTMLElement
    >;
    's-button': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        variant?: 'primary' | 'plain';
        href?: string;
        loading?: boolean;
      },
      HTMLElement
    >;
    's-progress-bar': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        value?: number;
        max?: number;
      },
      HTMLElement
    >;
    's-list-item': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement>,
      HTMLElement
    >;
    's-index-table': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement>,
      HTMLElement
    >;
    's-index-table-row': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & { onClick?: () => void },
      HTMLElement
    >;
    's-index-table-cell': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement>,
      HTMLElement
    >;
    's-skeleton-page': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement>,
      HTMLElement
    >;
    's-skeleton-body-text': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement>,
      HTMLElement
    >;
    's-nav-menu': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement>,
      HTMLElement
    >;
    's-collapsible': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & { title?: string },
      HTMLElement
    >;
    's-select': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        label?: string;
        value?: string;
        options?: string;
        onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
      },
      HTMLElement
    >;
    's-text-field': React.DetailedHTMLProps<
      React.HTMLAttributes<HTMLElement> & {
        label?: string;
        type?: string;
        value?: string;
        onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
      },
      HTMLElement
    >;
    }
  }
}
