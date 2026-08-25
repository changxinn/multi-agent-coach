import { z } from 'zod'
import { emailSchema, passwordSchema } from './common'

export const loginSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
})

export const userSchema = z.object({
  name: nameSchema,
  email: emailSchema,
  role: z.enum(['admin', 'user', 'manager']),
})

export type LoginInput = z.infer<typeof loginSchema>
export type UserInput = z.infer<typeof userSchema>
