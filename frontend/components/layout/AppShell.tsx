"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; icon: ReactNode };

const iconProps = {
  className: "h-[18px] w-[18px] shrink-0",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  "aria-hidden": true,
} as const;

const NAV_SECTIONS: { label: string; items: NavItem[] }[] = [
  {
    label: "Worklist",
    items: [
      {
        href: "/encounters",
        label: "Encounters",
        icon: (
          <svg viewBox="0 0 24 24" {...iconProps}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" />
          </svg>
        ),
      },
      {
        href: "/encounters/new",
        label: "New encounter",
        icon: (
          <svg viewBox="0 0 24 24" {...iconProps}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
        ),
      },
    ],
  },
  {
    label: "Ingestion",
    items: [
      {
        href: "/batches",
        label: "Batch ingestion",
        icon: (
          <svg viewBox="0 0 24 24" {...iconProps}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
          </svg>
        ),
      },
    ],
  },
];

function isActive(href: string, pathname: string): boolean {
  if (href === "/encounters") return pathname === "/encounters" || pathname.startsWith("/encounters/");
  if (href === "/batches") return pathname === "/batches" || pathname.startsWith("/batches/");
  return pathname === href;
}

function initials(name: string | undefined): string {
  if (!name) return "U";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-600 text-white shadow-sm"
        aria-hidden="true"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2.2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 5.5v13m-6.5-6.5h13" />
        </svg>
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold leading-tight text-white">Medical Billing Coder</p>
        <p className="truncate text-[11px] font-medium leading-tight text-brand-200">
          Revenue cycle workspace
        </p>
      </div>
    </div>
  );
}

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4" aria-label="Primary">
      {NAV_SECTIONS.map((section) => (
        <div key={section.label}>
          <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-brand-300">
            {section.label}
          </p>
          <ul className="space-y-1">
            {section.items.map((item) => {
              const active = isActive(item.href, pathname);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-400",
                      active
                        ? "bg-white/10 text-white"
                        : "text-brand-100 hover:bg-white/5 hover:text-white",
                    )}
                  >
                    {active ? (
                      <span
                        className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent-400"
                        aria-hidden="true"
                      />
                    ) : null}
                    <span className="text-brand-200">{item.icon}</span>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function UserMenu() {
  const { user, organization, logout } = useAuth();
  return (
    <div className="border-t border-white/10 p-3">
      <div className="flex items-center gap-3 rounded-lg px-2 py-1.5">
        <span
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-600/90 text-xs font-semibold text-white"
          aria-hidden="true"
        >
          {initials(user?.full_name)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-white">{user?.full_name ?? "Signed in"}</p>
          <p className="truncate text-xs text-brand-300">{organization?.name}</p>
        </div>
        <button
          type="button"
          onClick={() => void logout()}
          className="rounded-md px-2 py-1 text-xs font-medium text-brand-200 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-400"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, organization, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-surface">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col bg-brand-800 md:flex">
        <div className="border-b border-white/10 px-4 py-4">
          <BrandMark />
        </div>
        <NavLinks pathname={pathname} />
        <UserMenu />
      </aside>

      {/* Mobile top bar + nav */}
      <div className="flex min-w-0 flex-1 flex-col md:hidden">
        <header className="border-b border-white/10 bg-brand-800">
          <div className="flex items-center justify-between gap-3 px-4 py-3">
            <BrandMark />
            <div className="flex shrink-0 items-center gap-2">
              {user ? (
                <span
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-600/90 text-xs font-semibold text-white"
                  aria-hidden="true"
                >
                  {initials(user?.full_name)}
                </span>
              ) : null}
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-md px-2 py-1 text-xs font-medium text-brand-100 hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-400"
              >
                Sign out
              </button>
            </div>
          </div>
          <div className="border-t border-white/10 px-3 py-2">
            <nav className="flex gap-1 overflow-x-auto" aria-label="Primary">
              {NAV_SECTIONS.flatMap((s) => s.items).map((item) => {
                const active = isActive(item.href, pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-400",
                      active ? "bg-white/10 text-white" : "text-brand-100 hover:bg-white/5 hover:text-white",
                    )}
                  >
                    <span className="text-brand-300">{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </header>
        <main className="flex-1 p-4">{children}</main>
      </div>

      {/* Desktop content */}
      <div className="hidden min-w-0 flex-1 flex-col md:flex">
        <main className="flex-1 p-6 lg:p-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
