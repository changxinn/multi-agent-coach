import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Form, Input, Button, message } from 'antd'
import { exampleFormSchema, type ExampleFormInput } from './validators'

export function ExampleForm() {
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<ExampleFormInput>({
    resolver: zodResolver(exampleFormSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  })

  const onSubmit = async (data: ExampleFormInput) => {
    try {
      console.log('Form submitted:', data)
      message.success('Form submitted successfully!')
      reset()
    } catch (error) {
      console.error('Submission error:', error)
      message.error('Submission failed')
    }
  }

  return (
    <div className="max-w-md p-6">
      <h2 className="text-2xl font-bold mb-6">Login Form Example</h2>
      <Form layout="vertical" onFinish={handleSubmit(onSubmit)}>
        <Controller
          name="email"
          control={control}
          render={({ field }) => (
            <Form.Item
              label="Email"
              validateStatus={errors.email ? 'error' : ''}
              help={errors.email?.message}
            >
              <Input
                placeholder="Enter your email"
                {...field}
                size="large"
              />
            </Form.Item>
          )}
        />

        <Controller
          name="password"
          control={control}
          render={({ field }) => (
            <Form.Item
              label="Password"
              validateStatus={errors.password ? 'error' : ''}
              help={errors.password?.message}
            >
              <Input.Password
                placeholder="Enter your password"
                {...field}
                size="large"
              />
            </Form.Item>
          )}
        />

        <Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            loading={isSubmitting}
            size="large"
            block
          >
            Submit
          </Button>
        </Form.Item>
      </Form>
    </div>
  )
}
