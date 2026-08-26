import { useQuery } from '@tanstack/react-query'
import { Spin, Alert, Card, Button } from 'antd'
import { api } from '../../lib/api'

interface User {
  id: number
  name: string
  email: string
}

export function ExampleQuery() {
  const {
    data: users,
    isLoading,
    error,
    refetch,
  } = useQuery<User[]>({
    queryKey: ['users'],
    queryFn: () => api.get<User[]>('/users'),
    enabled: false,
  })

  if (isLoading) return <Spin size="large" />

  if (error) return <Alert message={(error as Error).message} type="error" showIcon />

  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">TanStack Query Example</h2>
      <Button onClick={() => refetch()} className="mb-4">
        Fetch Users
      </Button>
      {users && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {users.map((user) => (
            <Card key={user.id} title={user.name} className="shadow-sm">
              <p className="text-gray-600">{user.email}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
