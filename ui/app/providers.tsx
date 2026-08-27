"use client";

import { SaltProvider } from "@salt-ds/core";
import { WorkspaceProvider } from "@/src/components/WorkspaceProvider";

export function AppProviders({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <SaltProvider mode="light" density="medium">
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </SaltProvider>
  );
}
