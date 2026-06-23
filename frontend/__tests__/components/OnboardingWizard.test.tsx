import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NextIntlClientProvider } from 'next-intl'
import { OnboardingWizard } from '@/components/onboarding/OnboardingWizard'

// ── Mocks ──────────────────────────────────────────────────────
const mockPush = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('@/stores/uiStore', () => ({
  useUIStore: vi.fn(),
}))

vi.mock('next-intl', async () => {
  const actual = await vi.importActual('next-intl')
  return actual
})

import { useUIStore } from '@/stores/uiStore'

// ── Messages matching production en.json ──────────────────────
const messages = {
  onboarding: {
    step1: {
      title: 'Welcome to AStockPursue',
      description:
        'AI-powered quantitative research &amp; trading platform. Describe strategies in natural language, auto-backtest, one-click live trading.',
      button: 'Get Started',
    },
    step2: {
      title: 'Connect Broker',
      description:
        'Connect your broker account for live trading and portfolio management',
      button: 'Connect',
    },
    step3: {
      title: 'Create Strategy',
      description:
        'Design and backtest your quantitative trading strategies to discover market opportunities',
      button: 'Try It',
    },
    step4: {
      title: 'Run Backtest',
      description:
        'Validate strategy performance with historical data and optimize trading parameters',
      button: 'Complete',
    },
    skip: 'Skip',
    next: 'Next',
    complete: 'Complete',
    progress: 'Step {current} of {total}',
  },
}

// ── Helpers ────────────────────────────────────────────────────
function renderWithProviders(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  )
}

/** Get all 4 progress-dot container elements (the w-4 h-4 rounded-full divs) */
function getAllDotContainers(container: HTMLElement) {
  return container.querySelectorAll('.w-4.h-4.rounded-full')
}

// ── Tests ──────────────────────────────────────────────────────
describe('OnboardingWizard', () => {
  const mockSetOnboardingCompleted = vi.fn()
  const mockDismissOnboarding = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useUIStore).mockReturnValue({
      setOnboardingCompleted: mockSetOnboardingCompleted,
      dismissOnboarding: mockDismissOnboarding,
      sidebarCollapsed: false,
      toggleSidebar: vi.fn(),
      onboardingCompleted: false,
      onboardingDismissed: false,
      resetOnboarding: vi.fn(),
    })
  })

  // ── 1. Step 1 content ──────────────────────────────────────
  it('renders step 1 content with welcome title, description, and Get Started button', () => {
    renderWithProviders(<OnboardingWizard onComplete={vi.fn()} />)
    expect(screen.getByText('Welcome to AStockPursue')).toBeInTheDocument()
    expect(
      screen.getByText(/AI-powered quantitative research/)
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Get Started/ })
    ).toBeInTheDocument()
  })

  // ── 2. Get Started → step 2 ────────────────────────────────
  it('advances to step 2 when clicking Get Started', () => {
    renderWithProviders(<OnboardingWizard onComplete={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Get Started/ }))
    expect(screen.getByText('Connect Broker')).toBeInTheDocument()
    expect(
      screen.getByText(/Connect your broker account/)
    ).toBeInTheDocument()
  })

  // ── 3. Step 2 content + Connect button ─────────────────────
  it('step 2 shows Connect Broker content and button', () => {
    renderWithProviders(<OnboardingWizard onComplete={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Get Started/ }))
    expect(screen.getByText('Connect Broker')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Connect/ })
    ).toBeInTheDocument()
  })

  // ── 4. Connect button navigates & completes ────────────────
  it('step 2 Connect button navigates to /broker and calls onComplete', () => {
    const onComplete = vi.fn()
    renderWithProviders(<OnboardingWizard onComplete={onComplete} />)
    fireEvent.click(screen.getByRole('button', { name: /Get Started/ }))
    fireEvent.click(screen.getByRole('button', { name: /Connect/ }))
    expect(mockPush).toHaveBeenCalledWith('/broker')
    expect(mockSetOnboardingCompleted).toHaveBeenCalled()
    expect(onComplete).toHaveBeenCalled()
  })

  // ── 5. Skip dismisses & completes ──────────────────────────
  it('skip button calls dismissOnboarding and onComplete at step 1', () => {
    const onComplete = vi.fn()
    renderWithProviders(<OnboardingWizard onComplete={onComplete} />)
    fireEvent.click(screen.getByText('Skip'))
    expect(mockDismissOnboarding).toHaveBeenCalled()
    expect(onComplete).toHaveBeenCalled()
  })

  it('skip button calls dismissOnboarding and onComplete at step 2', () => {
    const onComplete = vi.fn()
    renderWithProviders(<OnboardingWizard onComplete={onComplete} />)
    fireEvent.click(screen.getByRole('button', { name: /Get Started/ }))
    fireEvent.click(screen.getByText('Skip'))
    expect(mockDismissOnboarding).toHaveBeenCalled()
    expect(onComplete).toHaveBeenCalled()
  })

  // ── 6. Progress dots ───────────────────────────────────────
  it('shows 4 progress dots', () => {
    const { container } = renderWithProviders(
      <OnboardingWizard onComplete={vi.fn()} />
    )
    const dots = getAllDotContainers(container)
    expect(dots.length).toBe(4)
  })

  it('step 1: first dot is active, remaining dots are pending', () => {
    const { container } = renderWithProviders(
      <OnboardingWizard onComplete={vi.fn()} />
    )
    const dots = getAllDotContainers(container)
    // Active dot has an inner filled div (w-1.5 h-1.5 rounded-full)
    // Pending dots have border-2 class

    // First dot should contain the active inner dot indicator
    const activeInner = dots[0].querySelector('.w-1\\.5.h-1\\.5.rounded-full')
    expect(activeInner).not.toBeNull()

    // Remaining dots should NOT have active inner indicator
    for (let i = 1; i < dots.length; i++) {
      expect(
        dots[i].querySelector('.w-1\\.5.h-1\\.5.rounded-full')
      ).toBeNull()
    }
  })

  it('step 2: first dot is visited, second dot is active', () => {
    const { container } = renderWithProviders(
      <OnboardingWizard onComplete={vi.fn()} />
    )
    fireEvent.click(screen.getByRole('button', { name: /Get Started/ }))

    const dots = getAllDotContainers(container)

    // First dot (visited): should contain a Check SVG icon (lucide)
    const firstDotSvg = dots[0].querySelector('svg')
    expect(firstDotSvg).not.toBeNull()

    // Second dot (active): should contain the active inner indicator
    const activeInner = dots[1].querySelector('.w-1\\.5.h-1\\.5.rounded-full')
    expect(activeInner).not.toBeNull()
  })

  // ── 7. Step indicator ──────────────────────────────────────
  it('shows correct step count at step 1', () => {
    renderWithProviders(<OnboardingWizard onComplete={vi.fn()} />)
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument()
  })

  it('shows correct step count at step 2', () => {
    renderWithProviders(<OnboardingWizard onComplete={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /Get Started/ }))
    expect(screen.getByText('Step 2 of 4')).toBeInTheDocument()
  })

  // ── 8. Step icon renders ───────────────────────────────────
  it('renders a step icon at step 1', () => {
    const { container } = renderWithProviders(
      <OnboardingWizard onComplete={vi.fn()} />
    )
    // The icon is a lucide SVG inside a decorative wrapper
    const iconWrappers = container.querySelectorAll('svg.w-10.h-10')
    expect(iconWrappers.length).toBeGreaterThanOrEqual(1)
  })
})
