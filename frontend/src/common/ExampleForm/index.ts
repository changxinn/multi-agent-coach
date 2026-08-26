/**
 * Barrel export file for ExampleForm component
 * 
 * Purpose: Provides clean imports from the folder root
 * Usage: import { ExampleForm } from '@/components/ExampleForm'
 * 
 * This avoids needing to specify the exact file path:
 * ❌ import { ExampleForm } from '@/components/ExampleForm/ExampleForm'
 * ✅ import { ExampleForm } from '@/components/ExampleForm'
 */

export { ExampleForm } from './ExampleForm'
export { exampleFormSchema } from './validators'
export type { ExampleFormInput } from './validators'
