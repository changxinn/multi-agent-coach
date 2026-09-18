const QUOTES = [
  'Discipline is choosing what you want most over what you want now.',
  'Slow progress is still progress — show up anyway.',
  'Train the body, fuel the work, protect the rest.',
  'Consistency beats intensity when intensity is random.',
  'You do not have to be extreme. You have to be honest.',
  'Recovery is part of the program, not a pause from it.',
  'Small reps, stacked daily, become the athlete you are becoming.',
]

export function quoteOfTheDay(date = new Date()): string {
  const utcDay = Math.floor(
    Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000
  )
  return QUOTES[((utcDay % QUOTES.length) + QUOTES.length) % QUOTES.length]
}
