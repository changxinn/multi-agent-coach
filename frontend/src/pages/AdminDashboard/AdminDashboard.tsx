import WidgetCard from '@/common/WidgetCard'
import RoleSummary from '@/common/RoleSummary'

function AdminDashboard() {
  return (
    <div className="page-shell">
      <RoleSummary
        role="Admin"
        summary="A high-level view for governance, compliance, and system health."
        focus="Protect operations with oversight and rapid decision-making."
      />

      <div className="widget-grid">
        <WidgetCard title="System uptime" value="99.98%" hint="Last 30 days" accent="teal" />
        <WidgetCard title="Security alerts" value="2" hint="No critical issues" accent="amber" />
        <WidgetCard title="Active users" value="1,842" hint="+8% this month" accent="violet" />
      </div>
    </div>
  )
}

export default AdminDashboard
