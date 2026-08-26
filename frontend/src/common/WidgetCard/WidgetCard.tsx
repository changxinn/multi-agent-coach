type WidgetCardProps = {
  title: string
  value: string
  hint: string
  accent?: 'blue' | 'violet' | 'teal' | 'amber'
}

function WidgetCard({ title, value, hint, accent = 'blue' }: WidgetCardProps) {
  return (
    <article className={`widget-card ${accent}`}>
      <p className="widget-label">{title}</p>
      <h3>{value}</h3>
      <span>{hint}</span>
    </article>
  )
}

export default WidgetCard
