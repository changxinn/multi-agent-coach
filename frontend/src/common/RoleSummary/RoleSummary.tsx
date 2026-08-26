type RoleSummaryProps = {
  role: string
  summary: string
  focus: string
}

function RoleSummary({ role, summary, focus }: RoleSummaryProps) {
  return (
    <section className="role-summary">
      <p className="eyebrow">Role persona</p>
      <h2>{role}</h2>
      <p>{summary}</p>
      <div className="focus-pill">{focus}</div>
    </section>
  )
}

export default RoleSummary
