export {};

declare global {
  interface Window {
    desktopApi?: {
      checkBackendHealth: () => Promise<{
        online: boolean;
        payload?: { status: string; version: string; timestamp: string };
        message?: string;
      }>;
      pickVaultFolder: () => Promise<{ canceled: boolean; path: string | null; error?: string }>;
      openVaultPicker?: () => Promise<{ canceled: boolean; path: string | null; error?: string }>;
      selectVault: (path: string) => Promise<{
        ok: boolean;
        payload?: {
          vault_path: string;
          exists: boolean;
          is_directory: boolean;
          has_obsidian: boolean;
          warning: string | null;
        };
        error?: string;
      }>;
      bootstrapVault: (path: string) => Promise<{ ok: boolean; payload?: unknown; error?: string }>;
      configureVault: (path: string) => Promise<{
        ok: boolean;
        payload?: {
          vault_path: string;
          has_obsidian: boolean;
          git_detected: boolean;
          obsidian_cli_available: boolean;
          warning: string | null;
        };
        error?: string;
      }>;
      vaultStatus: (path: string) => Promise<{
        ok: boolean;
        payload?: {
          vault_path: string;
          has_obsidian: boolean;
          git_detected: boolean;
          obsidian_cli_available: boolean;
        };
        error?: string;
      }>;
      testGroqKey: (vaultPath: string, apiKey: string) => Promise<{
        ok: boolean;
        payload?: { provider: string; connected: boolean; message: string };
        error?: string;
      }>;
      onBackendExited: (listener: (payload: { code: number | null }) => void) => void;
    };
  }
}
