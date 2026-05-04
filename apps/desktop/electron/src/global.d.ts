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
      groqStatus: (vaultPath: string) => Promise<{
        ok: boolean;
        payload?: {
          provider: string;
          configured: boolean;
          connected: boolean;
          message: string;
          default_text_model: string;
          cheap_fast_model: string;
          review_model: string;
          vision_model: string | null;
        };
        error?: string;
      }>;
      onBackendExited: (listener: (payload: { code: number | null }) => void) => void;
    };
  }
}
