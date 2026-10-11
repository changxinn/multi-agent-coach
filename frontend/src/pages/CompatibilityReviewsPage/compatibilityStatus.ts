export function compatibilityStatusColor(status: string) {
  switch (status) {
    case 'approved': return 'green'
    case 'rejected': return 'red'
    case 'review_required': return 'gold'
    default: return 'blue'
  }
}