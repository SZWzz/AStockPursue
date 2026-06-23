'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Rocket, Link, Brain, ChartBar, Check, ChevronRight } from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

const STEPS = [
  { icon: Rocket },
  { icon: Link },
  { icon: Brain },
  { icon: ChartBar },
] as const

interface OnboardingWizardProps {
  onComplete: () => void
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const t = useTranslations('onboarding')
  const router = useRouter()
  const { setOnboardingCompleted, dismissOnboarding } = useUIStore()
  const [step, setStep] = useState(0)
  const [visited, setVisited] = useState<Set<number>>(new Set([0]))

  const STEPS_CONFIG: Record<number, { link: string | null }> = {
    1: { link: '/broker' },
    2: { link: '/strategy-lab' },
    3: { link: null },
  }

  const handleSkip = () => {
    dismissOnboarding()
    onComplete()
  }

  const handlePrimary = () => {
    const visitedNext = new Set(visited)
    visitedNext.add(step)
    setVisited(visitedNext)

    if (step < 3) {
      const config = STEPS_CONFIG[step] as { link: string | null } | undefined
      if (config?.link) {
        setOnboardingCompleted()
        router.push(config.link)
        onComplete()
        return
      }
      setStep(step + 1)
      return
    }

    // Step 4 (index 3): complete onboarding
    setOnboardingCompleted()
    onComplete()
  }

  const StepIcon = STEPS[step].icon

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="max-w-lg w-full mx-4 rounded-2xl bg-[var(--card)] border border-[var(--border)] p-8 shadow-xl">
        {/* Progress dots */}
        <div className="flex items-center justify-center gap-3 mb-8">
          {STEPS.map((_, i) => {
            const isVisited = visited.has(i)
            const isActive = i === step
            return (
              <div
                key={i}
                className={cn(
                  'w-4 h-4 rounded-full flex items-center justify-center transition-all duration-300',
                  isVisited && !isActive
                    ? 'bg-[var(--primary)]/30'
                    : isActive
                      ? 'bg-[var(--primary)] ring-2 ring-[var(--primary)]/30'
                      : 'border-2 border-[var(--border)]'
                )}
              >
                {isVisited && !isActive && (
                  <Check className="w-2.5 h-2.5 text-[var(--primary)]" />
                )}
                {isActive && (
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary-foreground)]" />
                )}
              </div>
            )
          })}
        </div>

        {/* Step indicator text */}
        <p className="text-xs text-center text-[var(--muted-foreground)] mb-6 tracking-wider uppercase">
          {t('progress', { current: step + 1, total: STEPS.length })}
        </p>

        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="p-5 rounded-2xl bg-[var(--primary)]/10 ring-1 ring-[var(--primary)]/20">
            <StepIcon className="w-10 h-10 text-[var(--primary)]" strokeWidth={1.5} />
          </div>
        </div>

        {/* Title & Description */}
        <h2 className="text-xl font-semibold text-center mb-3 text-[var(--foreground)]">
          {t(`step${step + 1}.title`)}
        </h2>
        <p className="text-sm text-center text-[var(--muted-foreground)] mb-8 leading-relaxed px-2">
          {t(`step${step + 1}.description`)}
        </p>

        {/* Buttons */}
        <div className="flex items-center justify-between">
          <button
            onClick={handleSkip}
            className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors px-2 py-1"
          >
            {t('skip')}
          </button>
          <button
            onClick={handlePrimary}
            className="inline-flex items-center gap-1.5 px-6 py-2.5 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] font-medium text-sm hover:bg-[var(--primary)]/80 active:scale-[0.98] transition-all"
          >
            {t(`step${step + 1}.button`)}
            {step === 0 && <ChevronRight className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
