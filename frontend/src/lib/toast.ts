/**
 * Toast-Helper: Nutzt shopify.toast wenn in Embedded App, sonst console
 */
export function showToast(
  message: string,
  options?: { duration?: number; isError?: boolean }
) {
  if (typeof window !== 'undefined' && window.shopify?.toast?.show) {
    window.shopify.toast.show(message, options);
  } else {
    if (options?.isError) {
      console.error(message);
    } else {
      console.log(message);
    }
  }
}
