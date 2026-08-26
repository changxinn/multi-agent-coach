import { useState, useRef, useEffect } from 'react'
import './NotificationPopup.css'

export interface Notification {
  id: string
  title: string
  message: string
  timestamp: Date
  read: boolean
  type: 'info' | 'warning' | 'success' | 'error'
}

interface NotificationPopupProps {
  isOpen: boolean
  onClose: () => void
  notifications?: Notification[]
  onMarkAsRead?: (id: string) => void
  onMarkAllAsRead?: () => void
  unreadCount?: number
}

const defaultNotifications: Notification[] = [
  {
    id: '1',
    title: 'New Employee Added',
    message: 'John Doe has been added to the Engineering department',
    timestamp: new Date(Date.now() - 1000 * 60 * 5), // 5 minutes ago
    read: false,
    type: 'success',
  },
  {
    id: '2',
    title: 'Project Deadline',
    message: 'Q4 Report is due in 3 days',
    timestamp: new Date(Date.now() - 1000 * 60 * 60), // 1 hour ago
    read: false,
    type: 'warning',
  },
  {
    id: '3',
    title: 'System Update',
    message: 'Scheduled maintenance on Sunday 2 AM - 4 AM',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
    read: true,
    type: 'info',
  },
  {
    id: '4',
    title: 'Leave Request',
    message: 'Sarah Smith requested leave for next week',
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    read: false,
    type: 'info',
  },
]

export function NotificationPopup({
  isOpen,
  onClose,
  notifications = defaultNotifications,
  onMarkAsRead,
  onMarkAllAsRead,
  unreadCount: externalUnreadCount,
}: NotificationPopupProps) {
  const popupRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(event.target as Node)) {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen, onClose])

  const calculatedUnreadCount = externalUnreadCount ?? notifications.filter(n => !n.read).length

  const getTimeAgo = (date: Date): string => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000)
    
    if (seconds < 60) return 'Just now'
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
    return `${Math.floor(seconds / 86400)}d ago`
  }

  const getTypeStyles = (type: Notification['type']) => {
    switch (type) {
      case 'success':
        return { bg: 'bg-green-50', border: 'border-green-200', icon: '✓' }
      case 'warning':
        return { bg: 'bg-yellow-50', border: 'border-yellow-200', icon: '⚠' }
      case 'error':
        return { bg: 'bg-red-50', border: 'border-red-200', icon: '✕' }
      default:
        return { bg: 'bg-blue-50', border: 'border-blue-200', icon: 'ℹ' }
    }
  }

  if (!isOpen) return null

  return (
    <div
      ref={popupRef}
      className="notification-popup"
    >
      <div className="notification-header">
        <div className="notification-title">
          <h3>Notifications</h3>
          {calculatedUnreadCount > 0 && (
            <span className="unread-badge">{calculatedUnreadCount}</span>
          )}
        </div>
        {calculatedUnreadCount > 0 && (
          <button
            type="button"
            className="mark-all-read"
            onClick={onMarkAllAsRead}
          >
            Mark all as read
          </button>
        )}
      </div>

      <div className="notification-list">
        {notifications.length === 0 ? (
          <div className="no-notifications">
            <span>🔔</span>
            <p>No notifications yet</p>
          </div>
        ) : (
          notifications.map((notification) => {
            const styles = getTypeStyles(notification.type)
            return (
              <div
                key={notification.id}
                className={`notification-item ${!notification.read ? 'unread' : ''}`}
                onClick={() => onMarkAsRead?.(notification.id)}
              >
                <div className={`notification-icon ${styles.bg} ${styles.border}`}>
                  {styles.icon}
                </div>
                <div className="notification-content">
                  <div className="notification-meta">
                    <strong className="notification-title-text">
                      {notification.title}
                    </strong>
                    <span className="notification-time">
                      {getTimeAgo(notification.timestamp)}
                    </span>
                  </div>
                  <p className="notification-message">{notification.message}</p>
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="notification-footer">
        <button type="button" className="view-all">
          View all notifications
        </button>
      </div>
    </div>
  )
}

export default NotificationPopup
