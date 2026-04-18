/** ProfileContext — perfil de contribuyente persistido en Firestore por UID */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { doc, getDoc, setDoc, serverTimestamp, DocumentData } from 'firebase/firestore';
import { db } from '../services/firebase';
import { useAuth } from './AuthContext';
import type { ContributorType } from '../services/contributorProfiles';

export interface UserProfile {
  contributorType: ContributorType | null;
  rfc: string;
  regimen: string;
  nombre: string;
  actividad: string;
  cp: string;
  telefono: string;
  nombreNegocio: string;
  numEmpleados: string;
  onboardingComplete: boolean;
}

const DEFAULT_PROFILE: UserProfile = {
  contributorType: null,
  rfc: '',
  regimen: '',
  nombre: '',
  actividad: '',
  cp: '',
  telefono: '',
  nombreNegocio: '',
  numEmpleados: '',
  onboardingComplete: false,
};

const LEGACY_STORAGE_KEY = 'fiscalito_profile';

interface ProfileContextType {
  profile: UserProfile;
  loading: boolean;
  error: string | null;
  setProfile: (data: Partial<UserProfile>) => Promise<void>;
  isOnboardingComplete: () => boolean;
}

const ProfileContext = createContext<ProfileContextType | null>(null);

function userDocRef(uid: string) {
  return doc(db, 'users', uid);
}

/**
 * Maps legacy Firestore field names to current field names.
 * These legacy names (tipoContribuyente, actividadEconomica, codigoPostal,
 * onboardingCompleto) were used in an earlier schema version. This function
 * normalizes them so the rest of the app only deals with current names.
 * This is a one-time migration fallback — once the user saves their profile
 * again, the data is written with the current field names.
 */
function migrateLegacyFields(data: DocumentData): Partial<UserProfile> {
  const migrated: Partial<UserProfile> = {};

  if (data.tipoContribuyente !== undefined && data.contributorType === undefined) {
    migrated.contributorType = data.tipoContribuyente;
  }
  if (data.actividadEconomica !== undefined && data.actividad === undefined) {
    migrated.actividad = data.actividadEconomica;
  }
  if (data.codigoPostal !== undefined && data.cp === undefined) {
    migrated.cp = data.codigoPostal;
  }
  if (data.onboardingCompleto !== undefined && data.onboardingComplete === undefined) {
    migrated.onboardingComplete = data.onboardingCompleto;
  }

  return migrated;
}

/** Migrate legacy localStorage profile to Firestore for the given UID */
async function migrateLegacyLocalStorage(uid: string): Promise<UserProfile | null> {
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return null;

    const legacy = JSON.parse(raw) as Partial<UserProfile>;
    const profile = { ...DEFAULT_PROFILE, ...legacy };

    await setDoc(userDocRef(uid), {
      ...profile,
      updatedAt: serverTimestamp(),
    }, { merge: true });

    localStorage.removeItem(LEGACY_STORAGE_KEY);
    return profile;
  } catch {
    return null;
  }
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [profile, setProfileState] = useState<UserProfile>({ ...DEFAULT_PROFILE });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load profile from Firestore when user changes
  useEffect(() => {
    setProfileState({ ...DEFAULT_PROFILE });
    setError(null);

    // Si AuthContext aún no resuelve onAuthStateChanged, seguimos en loading.
    // Evita devolver DEFAULT_PROFILE con loading=false y disparar navegación
    // errónea al onboarding para un usuario realmente autenticado.
    if (authLoading) {
      setLoading(true);
      return;
    }

    if (!user) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        // 1. Check for legacy localStorage data and migrate
        const migrated = await migrateLegacyLocalStorage(user.uid);
        if (cancelled) return;

        if (migrated) {
          setProfileState(migrated);
          setLoading(false);
          return;
        }

        // 2. Load from Firestore
        const snap = await getDoc(userDocRef(user.uid));
        if (cancelled) return;

        if (snap.exists()) {
          const data = snap.data();
          const legacyOverrides = migrateLegacyFields(data);
          setProfileState({ ...DEFAULT_PROFILE, ...data, ...legacyOverrides } as UserProfile);
        }
        // If doc doesn't exist, keep DEFAULT_PROFILE (new user)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Error al cargar perfil');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [user, authLoading]);

  const setProfile = useCallback(async (data: Partial<UserProfile>) => {
    if (!user) return;

    const updated = { ...profile, ...data };
    setProfileState(updated);

    try {
      await setDoc(userDocRef(user.uid), {
        ...updated,
        updatedAt: serverTimestamp(),
      }, { merge: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al guardar perfil');
      throw err;
    }
  }, [user, profile]);

  const isOnboardingComplete = useCallback(() => profile.onboardingComplete, [profile]);

  return (
    <ProfileContext.Provider value={{ profile, loading, error, setProfile, isOnboardingComplete }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error('useProfile must be used within ProfileProvider');
  return ctx;
}
