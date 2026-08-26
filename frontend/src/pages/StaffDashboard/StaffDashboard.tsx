import WidgetCard from '../components/WidgetCard'
import RoleSummary from '../components/RoleSummary'

function StaffDashboard() {
  return (
    <div className="page-shell">
      <RoleSummary
        role="Staff"
        summary="A focused workspace for individual contributors managing their daily work."
        focus="Stay aligned with deadlines, tasks, and team updates."
      />

      <div className="widget-grid">
        <WidgetCard title="My tasks" value="11" hint="4 due today" accent="blue" />
        <WidgetCard title="Hours logged" value="38h" hint="Goal: 40h" accent="teal" />
        <WidgetCard title="Unread notes" value="3" hint="1 needs action" accent="amber" />
      </div>
    </div>
  )
}

export default StaffDashboard
