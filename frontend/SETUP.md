# Enterprise React Frontend Setup

## Installed Libraries

### Core Stack
- **TypeScript** - Type safety
- **Tailwind CSS v4** - Utility-first CSS
- **TanStack Query v5** - Data fetching & caching
- **Zustand** - Lightweight state management
- **Ant Design v6** - Enterprise UI components
- **React Hook Form v7** - Form handling
- **Zod** - Schema validation
- **@hookform/resolvers** - Zod integration with React Hook Form

## Project Structure

```
src/
├── components/
│   ├── ExampleForm.tsx       # React Hook Form + Zod example
│   ├── ExampleQuery.tsx      # TanStack Query example
│   ├── ExampleStore.tsx      # Zustand example
│   └── LibraryExamples.tsx   # Tabbed demo of all libraries
├── lib/
│   ├── api.ts                # API client for Java backend
│   ├── queryClient.ts        # TanStack Query configuration
│   ├── store.ts              # Zustand store setup
│   └── validators.ts         # Zod schemas
├── App.tsx
├── main.tsx                  # App entry with providers
└── index.css                 # Tailwind directives
```

## Configuration Files

- `tsconfig.json` - TypeScript config with path aliases (@/*)
- `vite.config.ts` - Vite config with React SWC plugin
- `tailwind.config.js` - Tailwind CSS config
- `postcss.config.js` - PostCSS with @tailwindcss/postcss
- `.env.example` - Environment variables template

## Setup Instructions

1. Copy `.env.example` to `.env` and update your Java backend URL:
   ```
   VITE_API_BASE_URL=http://localhost:8080/api
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start development server:
   ```bash
   npm run dev
   ```

4. Build for production:
   ```bash
   npm run build
   ```

## Usage Examples

### TanStack Query
```typescript
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'

const { data, isLoading } = useQuery({
  queryKey: ['users'],
  queryFn: () => api.get<User[]>('/users'),
})
```

### Zustand Store
```typescript
import { useAppStore } from '@/lib/store'

const { user, isAuthenticated, logout } = useAppStore()
```

### React Hook Form + Zod
```typescript
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { loginSchema } from '@/lib/validators'

const form = useForm({
  resolver: zodResolver(loginSchema),
})
```

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run Oxlint

## Notes

- Tailwind CSS v4 uses the new `@tailwindcss/postcss` plugin
- Ant Design is configured with custom theme in `main.tsx`
- Path alias `@/` resolves to `src/`
- API client automatically adds JSON content-type header
