import { Tabs } from 'antd'
import { ExampleForm } from '../ExampleForm'
import { ExampleQuery } from '../ExampleQuery'
import { ExampleStore } from '../ExampleStore'

export function LibraryExamples() {
  return (
    <div className="container mx-auto">
      <h1 className="font-bold mb-8">Library Integration Examples</h1>
      <Tabs
        items={[
          {
            key: 'form',
            label: 'React Hook Form + Zod',
            children: <ExampleForm />,
          },
          {
            key: 'query',
            label: 'TanStack Query',
            children: <ExampleQuery />,
          },
          {
            key: 'store',
            label: 'Zustand Store',
            children: <ExampleStore />,
          },
        ]}
      />
    </div>
  )
}
