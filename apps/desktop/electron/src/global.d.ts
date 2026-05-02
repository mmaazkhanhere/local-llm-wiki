export {};

declare global {
  interface Window {
    desktopApi?: {
      checkBackendHealth: () => Promise<{
        online: boolean;
        payload?: { status: string; version: string; timestamp: string };
        message?: string;
      }>;
      onBackendExited: (listener: (payload: { code: number | null }) => void) => void;
    };
  }
}
