import toast from 'react-hot-toast'

/** The one way to show a toast. It wraps react-hot-toast (whose <Toaster> in app/layout.tsx carries the token styling) so a screen never imports the library:
 *  one place to change how long a message stays, and an error stays longer than a success. A toast is for a result, never for a decision that must not be missed (use a Notice or a blocking Dialog). */
export const notify = {
  success: (message: string) => toast.success(message, { duration: 3000 }),
  error: (message: string) => toast.error(message, { duration: 6000 }),
  info: (message: string) => toast(message, { duration: 4000 }),
  dismiss: (id?: string) => toast.dismiss(id),
}
