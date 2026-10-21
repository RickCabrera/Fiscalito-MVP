/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FIREBASE_API_KEY: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN: string;
  readonly VITE_FIREBASE_PROJECT_ID: string;
  readonly VITE_FIREBASE_STORAGE_BUCKET: string;
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID: string;
  readonly VITE_FIREBASE_APP_ID: string;
  readonly VITE_FISCAL_AGENT_URL: string;
  // P6-01: datos del responsable para el aviso de privacidad y los términos.
  readonly VITE_RESPONSABLE_NOMBRE?: string;
  readonly VITE_RESPONSABLE_DOMICILIO?: string;
  readonly VITE_RESPONSABLE_CORREO?: string;
  readonly VITE_RESPONSABLE_FECHA_AVISO?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
