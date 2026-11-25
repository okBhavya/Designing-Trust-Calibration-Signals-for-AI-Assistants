/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEMO?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_CONSENT_VERSION?: string;
  readonly VITE_STUDY_ENROLLMENT_CODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
