import { api } from './api'

const base = '/nutrition-management'

export type Meal = { id: number; meal_type: string; description: string; calories: number | null; protein_g: number | null; carbs_g: number | null; fat_g: number | null; logged_at: string }
export type Profile = { timezone: string; dietary_preference: string; meals_per_day: number; activity_level: string; age: number | null; gender: string | null; weight_kg: number | null; height_cm: number | null; dietary_restrictions: string[]; allergies: string[] }
export type Target = { recommended_calories: number; macro_targets: Record<string, number>; effective_from?: string; version?: number }

export const nutritionManagementApi = {
  profile: () => api.post<Profile>(`${base}/profile/get`, {}),
  saveProfile: (payload: Profile) => api.post<Profile>(`${base}/profile/save`, payload),
  meals: () => api.post<{ items: Meal[]; total: number }>(`${base}/meals/list`, {}),
  createMeal: (payload: Omit<Meal, 'id' | 'logged_at'> & { logged_at?: string }) => api.post<Meal>(`${base}/meals/create`, payload),
  updateMeal: (payload: Meal) => api.post<Meal>(`${base}/meals/update`, payload),
  deleteMeal: (id: number) => api.post<void>(`${base}/meals/delete`, { id }),
  calculateTarget: (inputs: Record<string, unknown>) => api.post<Target>(`${base}/targets/calculate`, { inputs }),
  saveTarget: (inputs: Record<string, unknown>, effective_from: string) => api.post<Target>(`${base}/targets/save`, { inputs, effective_from }),
  currentTarget: () => api.post<Target>(`${base}/targets/current`, {}),
  foods: (q: string) => api.post<{ items: Array<{ fdc_id: number; name: string; calories: number | null; protein_g: number | null; carbs_g: number | null; fat_g: number | null }>; source: string }>(`${base}/foods/search`, { q }),
  assessments: () => api.post<{ items: Array<{ id: number; status: string; score: number; message: string; recommendations: string[]; created_at: string }> }>(`${base}/assessments/list`, {}),
}