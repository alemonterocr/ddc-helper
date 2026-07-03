interface StatusDotProps {
  status: 'ok' | 'warning' | 'error' | 'loading'
  label?: string
}

const DOT_CLASSES = {
  ok: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-destructive',
  loading: 'bg-muted-foreground animate-pulse',
}

export function StatusDot({ status, label }: StatusDotProps) {
  return (
    <span className="flex items-center gap-2">
      <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${DOT_CLASSES[status]}`} />
      {label && <span className="text-xs text-muted-foreground">{label}</span>}
    </span>
  )
}
