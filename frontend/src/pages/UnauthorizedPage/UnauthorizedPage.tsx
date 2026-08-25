import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/lib/authStore'
import './UnauthorizedPage.css'

export function UnauthorizedPage() {
  const navigate = useNavigate()
  const { logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="unauthorized-page">
      <div className="unauthorized-content">
        <h1>Unauthorized</h1>
        <p>You do not have permission to access this page.</p>
        <p>Your session has been cleared.</p>
        <button className="logout-button" onClick={handleLogout}>
          Return to Login
        </button>
      </div>
    </div>
  )
}
