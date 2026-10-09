import type { ReactNode } from 'react'
import { useId } from 'react'
export function Tooltip({ children, content }: { children: ReactNode; content: string }) {
  const id = useId()
  return <span className="tooltip-trigger" tabIndex={0} aria-describedby={id}>{children}<span className="tooltip" id={id} role="tooltip">{content}</span></span>
}
