import { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button, Typography } from 'antd'
import { BugOutlined, ReloadOutlined } from '@ant-design/icons'
import './ErrorBoundary.css'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('🚨 Error caught by ErrorBoundary:', error, errorInfo)
    
    this.setState({
      error,
      errorInfo,
    })

    // In production, you might want to send this to an error tracking service
    // Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } })
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleGoBack = () => {
    window.history.back()
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="h-full w-full flex items-center justify-center p-8 white-container error-boundary">
          <Result
            status="error"
            title="Oops! Something went wrong"
            subTitle={
              <div>
                <Typography.Paragraph className="text-sm">
                  A client-side error has occurred.
                </Typography.Paragraph>
              </div>
            }
            // icon={<BugOutlined className="text-6xl text-red-500" />}
            // extra={[
            //   <Button
            //     key="reload"
            //     type="primary"
            //     icon={<ReloadOutlined />}
            //     onClick={this.handleReload}
            //   >
            //     Reload Page
            //   </Button>,
            //   <Button
            //     key="back"
            //     onClick={this.handleGoBack}
            //   >
            //     Go Back
            //   </Button>,
            // ]}
            className="w-full max-w-2xl"
          />
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
