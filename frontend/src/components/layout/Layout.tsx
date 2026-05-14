/**
 * App shell: ambient background mesh, desktop sidebar, mobile top bar + drawer,
 * and routed page content via `AnimatedOutlet` (child routes render inside `<main>`).
 */
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';
import { AnimatedOutlet } from './AnimatedOutlet';

export function Layout() {
  return (
    <div className="relative flex min-h-screen overflow-x-hidden bg-[var(--color-background)]">
      {/* Decorative gradient layer; pointer-events none so it never steals clicks */}
      <div className="pointer-events-none fixed inset-0 premalytics-bg-mesh" aria-hidden />
      <div className="relative z-10 flex min-h-screen w-full">
        <div className="hidden lg:block">
          <Sidebar />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <Navbar />
          <main className="relative flex flex-1 flex-col overflow-x-hidden p-4 sm:p-6 lg:p-8">
            <AnimatedOutlet />
          </main>
        </div>
      </div>
    </div>
  );
}
