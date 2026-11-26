import { createDemoApi, createHttpApi, parseCondition, type StudyApi } from './api';

/** Build-time settings (Vite env). None of them is a secret: they are all in the public bundle. */
export const env = {
  demo: import.meta.env.VITE_DEMO === '1',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
  consentVersion: import.meta.env.VITE_CONSENT_VERSION || '2026-11-04',
  enrollmentCode: import.meta.env.VITE_STUDY_ENROLLMENT_CODE || '',
};

/** The study link carries the enrollment code as ?code=…; demo links may pick a condition with ?condition=A. */
export function readLinkParams(search: string = window.location.search) {
  const params = new URLSearchParams(search);
  return {
    code: params.get('code') || env.enrollmentCode,
    condition: parseCondition(params.get('condition')),
  };
}

export function createApi(): StudyApi {
  return env.demo ? createDemoApi(readLinkParams().condition) : createHttpApi(env.apiBaseUrl);
}
